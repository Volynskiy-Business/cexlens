import pytest

from cexlatency.metrics import confidence, percentile, summarize


def test_percentiles_interpolate():
    assert percentile([1, 2, 3, 4], 0.5) == 2.5
    assert percentile([1, 2, 3, 4], 0.95) == pytest.approx(3.85)


def test_summary_contains_robust_and_tail_metrics():
    result = summarize([10, 11, 12, 13, None], total_count=5)
    assert result["median"] == 11.5
    assert result["p50"] == 11.5
    assert result["p95"] == pytest.approx(12.85)
    assert result["failure_count"] == 1
    assert result["success_rate"] == 0.8
    assert "mad" in result and "jitter" in result


def test_confidence_fails_closed():
    assert confidence(2, 1.0) == "INSUFFICIENT"
    assert confidence(20, 1.0, 6, "VERIFIED", 1800) == "HIGH"
    assert confidence(20, 1.0, 6, "VERIFIED", 60) == "MEDIUM"
    assert confidence(200, 1.0, 1, "VERIFIED") == "MEDIUM"
