from __future__ import annotations

from collections import Counter, defaultdict
import statistics
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


def _behavior_label(confidence_level: str, speed: float, stability: float) -> str:
    if confidence_level == "INSUFFICIENT":
        return "insufficient_evidence"
    if speed >= 70 and stability < 40:
        return "fast_but_unstable"
    if stability >= 70 and speed < 40:
        return "stable_but_slower"
    if speed < 40 and stability < 40:
        return "consistently_poor"
    return "balanced"


def rank(samples: list[dict[str, Any]], websocket_rows: list[dict[str, Any]], exchange_ids: list[str], weights: dict[str,float], market_rows: list[dict[str, Any]] | None = None, window_count: int = 1, required_symbol_count: int = 3) -> list[dict[str, Any]]:
    grouped: dict[str,list[dict[str,Any]]]=defaultdict(list)
    for s in samples: grouped[s["exchange_id"]].append(s)
    ws_grouped: dict[str,list[dict[str,Any]]]=defaultdict(list)
    for row in websocket_rows: ws_grouped[row["exchange_id"]].append(row)
    market_grouped: dict[str,list[dict[str,Any]]]=defaultdict(list)
    market_all: dict[str,list[dict[str,Any]]]=defaultdict(list)
    for row in market_rows or []:
        market_all[row["exchange_id"]].append(row)
        if row.get("success"): market_grouped[row["exchange_id"]].append(row)
    raw: dict[str,dict[str,Any]]={}
    for ex in exchange_ids:
        rest=[s for s in grouped[ex] if s["probe_type"] in {"rest_reuse","rest_fresh"}]
        stat=summarize([s["duration_ms"] if s["success"] else None for s in rest],len(rest))
        rest_by_run: dict[str,list[dict[str,Any]]]=defaultdict(list)
        for sample in rest: rest_by_run[str(sample.get("run_id","single"))].append(sample)
        window_p95=[]
        for run_rows in rest_by_run.values():
            values=[float(sample["duration_ms"]) for sample in run_rows if sample.get("success") and sample.get("duration_ms") is not None]
            if values: window_p95.append(percentile(values,.95))
        cross_window_cv=(statistics.pstdev(window_p95)/statistics.fmean(window_p95)) if len(window_p95)>1 and statistics.fmean(window_p95) else 0.0 if window_p95 else None
        tcp=[s for s in grouped[ex] if s["probe_type"]=="tcp"]
        tcp_stat=summarize([s["duration_ms"] if s["success"] else None for s in tcp],len(tcp))
        ws_rows=ws_grouped[ex]
        def ws_average(key: str) -> float | None:
            values=[float(row[key]) for row in ws_rows if row.get(key) is not None]
            return sum(values)/len(values) if values else None
        qualities=[row.get("timestamp_quality") for row in ws_rows if row.get("timestamp_quality")]
        quality_counts=dict(Counter(str(value) for value in qualities))
        ws_messages=sum(int(row.get("messages",0)) for row in ws_rows)
        ws_observation_seconds=sum(float(row.get("observation_seconds",0) or 0) for row in ws_rows)
        ws_bad_events=sum(int(row.get(key,0)) for row in ws_rows for key in ("malformed_messages","sequence_gaps","duplicate_messages","stale_periods"))
        ws_success_count=sum(bool(row.get("success")) for row in ws_rows)
        ws_success_rate=ws_success_count/len(ws_rows) if ws_rows else 0.0
        ws_disconnects=sum(int(row.get("disconnects",0)) for row in ws_rows)
        ws_instability=100*(1-ws_success_rate)+25*ws_disconnects/max(len(ws_rows),1)+100*ws_bad_events/max(ws_messages,1)
        aggregate_quality="VERIFIED" if qualities and all(q=="VERIFIED" for q in qualities) else (str(qualities[0]) if len(set(qualities))==1 else "MIXED" if qualities else "UNKNOWN")
        w={"handshake_ms":ws_average("handshake_ms"),"ack_ms":ws_average("ack_ms"),"first_message_ms":ws_average("first_message_ms"),"p95_interval_ms":ws_average("p95_interval_ms"),"disconnects":ws_disconnects,"reconnect_ms":ws_average("reconnect_ms"),"heartbeat_rtt_ms":ws_average("heartbeat_rtt_ms"),"message_rate_hz":ws_average("message_rate_hz"),"median_observed_lag_ms":ws_average("median_observed_lag_ms"),"timestamp_quality":aggregate_quality}
        markets=market_grouped[ex]
        all_markets=market_all[ex]
        market_success_rate=sum(bool(row.get("success")) for row in all_markets)/len(all_markets) if all_markets else 0.0
        network_rows=[sample for sample in grouped[ex] if sample["probe_type"].startswith(("dns_","tcp","tls_"))]
        network_success_rate=sum(bool(sample.get("success")) for sample in network_rows)/len(network_rows) if network_rows else 0.0
        endpoint_pairs={(sample["probe_type"],sample["endpoint"]) for sample in network_rows}
        successful_pairs={(sample["probe_type"],sample["endpoint"]) for sample in network_rows if sample.get("success")}
        endpoint_coverage=len(successful_pairs)/len(endpoint_pairs) if endpoint_pairs else 0.0
        combined_success_rate=min(float(stat.get("success_rate",0)),ws_success_rate,market_success_rate,network_success_rate)
        spreads=[m["spread_bps"] for m in markets if m.get("spread_bps") is not None]
        depths=[(m.get("bid_depth_10bps") or 0)+(m.get("ask_depth_10bps") or 0) for m in markets]
        volumes=[m["quote_volume_24h"] for m in markets if m.get("quote_volume_24h") is not None]
        trade_frequencies=[m["trade_frequency_hz"] for m in markets if m.get("trade_frequency_hz") is not None]
        counts=[m["futures_market_count"] for m in markets if m.get("futures_market_count") is not None]
        raw[ex]={"tcp_median":tcp_stat.get("median"),"rest_median":stat.get("median"),"rest_p95":stat.get("p95"),"rest_p99":stat.get("p99"),"jitter":stat.get("jitter"),"success_rate":stat.get("success_rate",0.0),"combined_success_rate":combined_success_rate,"network_success_rate":network_success_rate,"endpoint_coverage":endpoint_coverage,"cross_window_rest_p95_cv":cross_window_cv,"sample_count":stat.get("success_count",0),"ws_handshake_ms":w.get("handshake_ms"),"ws_ack_ms":w.get("ack_ms"),"ws_first_message_ms":w.get("first_message_ms"),"ws_interval_p95":w.get("p95_interval_ms"),"ws_disconnects":w.get("disconnects",0),"ws_reconnect_ms":w.get("reconnect_ms"),"ws_heartbeat_rtt_ms":w.get("heartbeat_rtt_ms"),"ws_message_rate_hz":w.get("message_rate_hz"),"ws_sessions":len(ws_rows),"ws_observation_seconds":ws_observation_seconds,"ws_symbol_count":len({row.get("symbol") for row in ws_rows if row.get("success") and row.get("symbol")}),"ws_success_rate":ws_success_rate,"ws_messages":ws_messages,"ws_bad_events":ws_bad_events,"ws_instability":ws_instability if ws_rows else None,"observed_lag_ms":w.get("median_observed_lag_ms"),"timestamp_quality":w.get("timestamp_quality"),"timestamp_quality_counts":quality_counts,"market_success_rate":market_success_rate,"spread_bps":sum(spreads)/len(spreads) if spreads else None,"depth_10bps":sum(depths)/len(depths) if depths else None,"quote_volume_24h":sum(volumes)/len(volumes) if volumes else None,"trade_frequency_hz":sum(trade_frequencies)/len(trade_frequencies) if trade_frequencies else None,"market_count":max(counts) if counts else None,"market_symbols":len({m.get("symbol") for m in markets if m.get("symbol")})}
    spread_score=_lower_is_better({e:r["spread_bps"] for e,r in raw.items()})
    depth_score=_higher_is_better({e:(__import__("math").log1p(r["depth_10bps"]) if r["depth_10bps"] is not None else None) for e,r in raw.items()})
    volume_score=_higher_is_better({e:(__import__("math").log1p(r["quote_volume_24h"]) if r["quote_volume_24h"] is not None else None) for e,r in raw.items()})
    trade_frequency_score=_higher_is_better({e:(__import__("math").log1p(r["trade_frequency_hz"]) if r["trade_frequency_hz"] is not None else None) for e,r in raw.items()})
    ws_speed_score=_lower_is_better({e:r["ws_first_message_ms"] for e,r in raw.items()})
    ws_stability_score=_lower_is_better({e:r["ws_instability"] for e,r in raw.items()})
    dims={
      "rest_p95":_lower_is_better({e:r["rest_p95"] for e,r in raw.items()}),
      "tail_stability":_lower_is_better({e:(r["rest_p99"] or 0)+(r["jitter"] or 0) if r["rest_p99"] is not None else None for e,r in raw.items()}),
      "websocket":{e:0.4*ws_speed_score[e]+0.6*ws_stability_score[e] for e in raw},
      "freshness":_lower_is_better({e:r["ws_interval_p95"] for e,r in raw.items()}),
      "reliability":{e:100*r["combined_success_rate"]/(1+r["ws_disconnects"]/max(r["ws_sessions"],1)) for e,r in raw.items()},
      "market_quality":{e:(0.4*spread_score[e]+0.2*depth_score[e]+0.2*volume_score[e]+0.2*trade_frequency_score[e] if raw[e]["market_symbols"] else 0.0) for e in raw},"market_breadth":_higher_is_better({e:r["market_count"] for e,r in raw.items()}),"accessibility":{e:100*r["combined_success_rate"] for e,r in raw.items()},
    }
    rows=[]
    for ex,r in raw.items():
        conf=confidence(int(r["sample_count"]),float(r["combined_success_rate"]),window_count,str(r["timestamp_quality"]),float(r["ws_observation_seconds"]))
        components={name:round(scores[ex],2) for name,scores in dims.items()}
        evidence=(r["rest_p95"] is not None, r["ws_first_message_ms"] is not None, r["ws_interval_p95"] is not None, r["ws_symbol_count"] >= required_symbol_count, r["market_symbols"] >= required_symbol_count, r["trade_frequency_hz"] is not None, r["market_count"] is not None, r["endpoint_coverage"] >= .8)
        coverage=sum(evidence)/len(evidence)
        if coverage < 1.0: conf="INSUFFICIENT"
        elif window_count>=6 and r["cross_window_rest_p95_cv"] is not None:
            if r["cross_window_rest_p95_cv"]>1.0: conf="INSUFFICIENT"
            elif r["cross_window_rest_p95_cv"]>.5: conf="LOW"
        score=sum(weights.get(k,0)*v for k,v in components.items())*coverage
        if conf=="INSUFFICIENT": score=min(score,49.0)
        rows.append({"exchange_id":ex,"overall_score":round(score,1),"confidence":conf,"behavior_label":_behavior_label(conf,components["rest_p95"],components["tail_stability"]),"components":components,"raw_metrics":r,"evidence_coverage":coverage})
    return sorted(rows,key=lambda x:(x["confidence"]!="INSUFFICIENT",x["evidence_coverage"]>=.8,x["overall_score"]),reverse=True)
