from __future__ import annotations

from collections import defaultdict
from typing import Any

from .metrics import confidence, summarize


def _lower_is_better(values: dict[str, float | None]) -> dict[str, float]:
    present=[v for v in values.values() if v is not None]
    if not present: return {k: 0.0 for k in values}
    lo,hi=min(present),max(present)
    if hi==lo: return {k:(100.0 if v is not None else 0.0) for k,v in values.items()}
    return {k:(100*(hi-float(v))/(hi-lo) if v is not None else 0.0) for k,v in values.items()}


def rank(samples: list[dict[str, Any]], websocket_rows: list[dict[str, Any]], exchange_ids: list[str], weights: dict[str,float]) -> list[dict[str, Any]]:
    grouped: dict[str,list[dict[str,Any]]]=defaultdict(list)
    for s in samples: grouped[s["exchange_id"]].append(s)
    ws={r["exchange_id"]:r for r in websocket_rows}
    raw: dict[str,dict[str,Any]]={}
    for ex in exchange_ids:
        rest=[s for s in grouped[ex] if s["probe_type"].startswith("rest")]
        stat=summarize([s["duration_ms"] if s["success"] else None for s in rest],len(rest))
        w=ws.get(ex,{})
        raw[ex]={"rest_median":stat.get("median"),"rest_p95":stat.get("p95"),"rest_p99":stat.get("p99"),"jitter":stat.get("jitter"),"success_rate":stat.get("success_rate",0.0),"sample_count":stat.get("success_count",0),"ws_first_message_ms":w.get("first_message_ms"),"ws_interval_p95":w.get("p95_interval_ms"),"ws_disconnects":w.get("disconnects",0),"observed_lag_ms":w.get("median_observed_lag_ms")}
    dims={
      "rest_p95":_lower_is_better({e:r["rest_p95"] for e,r in raw.items()}),
      "tail_stability":_lower_is_better({e:(r["rest_p99"] or 0)+(r["jitter"] or 0) if r["rest_p99"] is not None else None for e,r in raw.items()}),
      "websocket":_lower_is_better({e:r["ws_first_message_ms"] for e,r in raw.items()}),
      "freshness":_lower_is_better({e:r["ws_interval_p95"] for e,r in raw.items()}),
      "reliability":{e:100*r["success_rate"]/(1+r["ws_disconnects"]) for e,r in raw.items()},
      "market_quality":{e:50.0 for e in raw},"market_breadth":{e:50.0 for e in raw},"accessibility":{e:100*r["success_rate"] for e,r in raw.items()},
    }
    rows=[]
    for ex,r in raw.items():
        conf=confidence(int(r["sample_count"]),float(r["success_rate"]),1,"UNKNOWN")
        components={name:round(scores[ex],2) for name,scores in dims.items()}
        coverage=sum(1 for name in ("rest_p95","websocket","freshness","reliability") if components[name]>0)/4
        score=sum(weights.get(k,0)*v for k,v in components.items())*coverage
        if conf=="INSUFFICIENT": score=min(score,49.0)
        rows.append({"exchange_id":ex,"overall_score":round(score,1),"confidence":conf,"components":components,"raw_metrics":r,"evidence_coverage":coverage})
    return sorted(rows,key=lambda x:x["overall_score"],reverse=True)

