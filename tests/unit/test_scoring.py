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


def test_incomplete_exchange_cannot_outrank_complete_evidence():
    samples=[sample("complete",x) for x in range(10,30)]+[sample("incomplete",1)]
    ws=[{"exchange_id":"complete","first_message_ms":50,"p95_interval_ms":10,"disconnects":0}]
    markets=[{"exchange_id":"complete","success":True,"spread_bps":1,"bid_depth_10bps":100,"ask_depth_10bps":100,"quote_volume_24h":1000,"futures_market_count":10} for _ in range(3)]
    result=rank(samples,ws,["complete","incomplete"],ScoringConfig().weights,markets)
    assert result[0]["exchange_id"] == "complete"
    assert result[1]["confidence"] == "INSUFFICIENT"
