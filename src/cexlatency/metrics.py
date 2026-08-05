from __future__ import annotations

import math
import statistics
from typing import Iterable


def percentile(values: list[float], p: float) -> float:
    if not values:
        raise ValueError("percentile requires values")
    ordered = sorted(values)
    rank = (len(ordered) - 1) * p
    lo, hi = math.floor(rank), math.ceil(rank)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (rank - lo)


def summarize(values: Iterable[float | None], total_count: int | None = None) -> dict[str, float | int]:
    clean = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    total = total_count if total_count is not None else len(clean)
    failures = max(0, total - len(clean))
    if not clean:
        return {"count": total, "success_count": 0, "failure_count": failures, "success_rate": 0.0}
    med = statistics.median(clean)
    deviations = [abs(v - med) for v in clean]
    p75, p90, p95, p99 = (percentile(clean, p) for p in (0.75, 0.90, 0.95, 0.99))
    std = statistics.pstdev(clean) if len(clean) > 1 else 0.0
    mad = statistics.median(deviations)
    threshold = med + 3 * max(mad, 0.001)
    return {
        "count": total, "success_count": len(clean), "failure_count": failures,
        "success_rate": len(clean) / total if total else 0.0,
        "min": min(clean), "max": max(clean), "mean": statistics.fmean(clean), "median": med,
        "p75": p75, "p90": p90, "p95": p95, "p99": p99, "stddev": std, "mad": mad,
        "coefficient_of_variation": std / statistics.fmean(clean) if statistics.fmean(clean) else 0.0,
        "jitter": statistics.fmean(abs(b - a) for a, b in zip(clean, clean[1:])) if len(clean) > 1 else 0.0,
        "outlier_count": sum(v > threshold for v in clean),
    }


def confidence(sample_count: int, success_rate: float, windows: int = 1, timestamp_quality: str = "UNKNOWN") -> str:
    if sample_count < 3 or success_rate < 0.5:
        return "INSUFFICIENT"
    points = min(sample_count / 20, 1.0) * 0.45 + success_rate * 0.35 + min(windows / 6, 1.0) * 0.15
    points += 0.05 if timestamp_quality == "VERIFIED" else 0.0
    if points >= 0.85:
        return "HIGH"
    if points >= 0.60:
        return "MEDIUM"
    return "LOW"

