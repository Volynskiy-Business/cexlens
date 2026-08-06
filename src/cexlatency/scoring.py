from __future__ import annotations

from collections import defaultdict
from typing import Any

from .metrics import confidence, summarize
from .metrics import percentile


def _lower_is_better(values: dict[str, float | None]) -> dict[str, float]:
    present=[v for v in values.values() if v is not None]
    if not present: return {k: 0.0 for k in values}
    lo,hi=percentile(present,.10),percentile(present,.90)
    if hi==lo: return {k:(100.0 if v is not None else 0.0) for k,v in values.items()}
    return {k:(max(0.0,min(100.0,100*(hi-float(v))/(hi-lo))) if v is not None else 0.0) for k,v in values.items()}


def _higher_is_better(values: dict[str, float | None]) -> dict[str, float]:
    present=[v for v in values.values() if v is not None]
    if not present: return {k:0.0 for k in values}
    lo,hi=percentile(present,.10),percentile(present,.90)
    if hi==lo: return {k:(100.0 if v is not None else 0.0) for k,v in values.items()}
    return {k:(max(0.0,min(100.0,100*(float(v)-lo)/(hi-lo))) if v is not None else 0.0) for k,v in values.items()}


def rank(samples: list[dict[str, Any]], websocket_rows: list[dict[str, Any]], exchange_ids: list[str], weights: dict[str,float], market_rows: list[dict[str, Any]] | None = None, window_count: int = 1) -> list[dict[str, Any]]:
    grouped: dict[str,list[dict[str,Any]]]=defaultdict(list)
    for s in samples: grouped[s["exchange_id"]].append(s)
    ws_grouped: dict[str,list[dict[str,Any]]]=defaultdict(list)
    for row in websocket_rows: ws_grouped[row["exchange_id"]].append(row)
    market_grouped: dict[str,list[dict[str,Any]]]=defaultdict(list)
    for row in market_rows or []:
        if row.get("success"): market_grouped[row["exchange_id"]].append(row)
    raw: dict[str,dict[str,Any]]={}
    for ex in exchange_ids:
        rest=[s for s in grouped[ex] if s["probe_type"] in {"rest_reuse","rest_fresh"}]
        stat=summarize([s["duration_ms"] if s["success"] else None for s in rest],len(rest))
        tcp=[s for s in grouped[ex] if s["probe_type"]=="tcp"]
        tcp_stat=summarize([s["duration_ms"] if s["success"] else None for s in tcp],len(tcp))
        ws_rows=ws_grouped[ex]
        def ws_average(key: str) -> float | None:
            values=[float(row[key]) for row in ws_rows if row.get(key) is not None]
            return sum(values)/len(values) if values else None
        qualities=[row.get("timestamp_quality") for row in ws_rows if row.get("timestamp_quality")]
        w={"first_message_ms":ws_average("first_message_ms"),"p95_interval_ms":ws_average("p95_interval_ms"),"disconnects":sum(int(row.get("disconnects",0)) for row in ws_rows),"reconnect_ms":ws_average("reconnect_ms"),"median_observed_lag_ms":ws_average("median_observed_lag_ms"),"timestamp_quality":"VERIFIED" if qualities and all(q=="VERIFIED" for q in qualities) else "UNKNOWN"}
        markets=market_grouped[ex]
        spreads=[m["spread_bps"] for m in markets if m.get("spread_bps") is not None]
        depths=[(m.get("bid_depth_10bps") or 0)+(m.get("ask_depth_10bps") or 0) for m in markets]
        volumes=[m["quote_volume_24h"] for m in markets if m.get("quote_volume_24h") is not None]
        counts=[m["futures_market_count"] for m in markets if m.get("futures_market_count") is not None]
        raw[ex]={"tcp_median":tcp_stat.get("median"),"rest_median":stat.get("median"),"rest_p95":stat.get("p95"),"rest_p99":stat.get("p99"),"jitter":stat.get("jitter"),"success_rate":stat.get("success_rate",0.0),"sample_count":stat.get("success_count",0),"ws_first_message_ms":w.get("first_message_ms"),"ws_interval_p95":w.get("p95_interval_ms"),"ws_disconnects":w.get("disconnects",0),"ws_reconnect_ms":w.get("reconnect_ms"),"observed_lag_ms":w.get("median_observed_lag_ms"),"timestamp_quality":w.get("timestamp_quality"),"spread_bps":sum(spreads)/len(spreads) if spreads else None,"depth_10bps":sum(depths)/len(depths) if depths else None,"quote_volume_24h":sum(volumes)/len(volumes) if volumes else None,"market_count":max(counts) if counts else None,"market_symbols":len(markets)}
    spread_score=_lower_is_better({e:r["spread_bps"] for e,r in raw.items()})
    depth_score=_higher_is_better({e:(__import__("math").log1p(r["depth_10bps"]) if r["depth_10bps"] is not None else None) for e,r in raw.items()})
    volume_score=_higher_is_better({e:(__import__("math").log1p(r["quote_volume_24h"]) if r["quote_volume_24h"] is not None else None) for e,r in raw.items()})
    dims={
      "rest_p95":_lower_is_better({e:r["rest_p95"] for e,r in raw.items()}),
      "tail_stability":_lower_is_better({e:(r["rest_p99"] or 0)+(r["jitter"] or 0) if r["rest_p99"] is not None else None for e,r in raw.items()}),
      "websocket":_lower_is_better({e:r["ws_first_message_ms"] for e,r in raw.items()}),
      "freshness":_lower_is_better({e:r["ws_interval_p95"] for e,r in raw.items()}),
      "reliability":{e:100*r["success_rate"]/(1+r["ws_disconnects"]) for e,r in raw.items()},
      "market_quality":{e:(0.5*spread_score[e]+0.25*depth_score[e]+0.25*volume_score[e] if raw[e]["market_symbols"] else 0.0) for e in raw},"market_breadth":_higher_is_better({e:r["market_count"] for e,r in raw.items()}),"accessibility":{e:100*r["success_rate"] for e,r in raw.items()},
    }
    rows=[]
    for ex,r in raw.items():
        conf=confidence(int(r["sample_count"]),float(r["success_rate"]),window_count,str(r["timestamp_quality"]))
        components={name:round(scores[ex],2) for name,scores in dims.items()}
        evidence=(r["rest_p95"] is not None, r["ws_first_message_ms"] is not None, r["ws_interval_p95"] is not None, r["market_symbols"] >= 3, r["market_count"] is not None)
        coverage=sum(evidence)/len(evidence)
        if coverage < .8: conf="INSUFFICIENT"
        score=sum(weights.get(k,0)*v for k,v in components.items())*coverage
        if conf=="INSUFFICIENT": score=min(score,49.0)
        rows.append({"exchange_id":ex,"overall_score":round(score,1),"confidence":conf,"components":components,"raw_metrics":r,"evidence_coverage":coverage})
    return sorted(rows,key=lambda x:(x["confidence"]!="INSUFFICIENT",x["evidence_coverage"]>=.8,x["overall_score"]),reverse=True)
