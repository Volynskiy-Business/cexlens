from cexlatency.config import ScoringConfig
from cexlatency.scoring import rank


def sample(exchange, duration, success=True):
    return {"exchange_id": exchange, "probe_type": "rest_reuse", "duration_ms": duration, "success": success}


def test_lower_tail_wins_when_evidence_is_equal():
    samples = [sample("fast", x) for x in (10, 11, 12)] + [sample("slow", x) for x in (20, 25, 30)]
    result = rank(samples, [], ["fast", "slow"], ScoringConfig().weights)
    assert result[0]["exchange_id"] == "fast"


def test_missing_data_is_penalized_and_insufficient():
    result = rank([], [], ["empty"], ScoringConfig().weights)[0]
    assert result["confidence"] == "INSUFFICIENT"
    assert result["overall_score"] <= 49

