from cexlatency.config import ScoringConfig
from cexlatency.scoring import _behavior_label, _lower_is_better, rank


def sample(exchange, duration, success=True, run_id="run"):
    return {"run_id":run_id,"exchange_id": exchange, "probe_type": "rest_reuse", "endpoint":"https://example.test", "duration_ms": duration, "success": success}


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
    ws=[{"exchange_id":"complete","symbol":symbol,"success":True,"first_message_ms":50,"p95_interval_ms":10,"disconnects":0,"messages":100} for symbol in ("BTCUSDT","ETHUSDT","SOLUSDT")]
    markets=[{"exchange_id":"complete","symbol":symbol,"success":True,"spread_bps":1,"bid_depth_10bps":100,"ask_depth_10bps":100,"quote_volume_24h":1000,"trade_frequency_hz":10,"futures_market_count":10} for symbol in ("BTCUSDT","ETHUSDT","SOLUSDT")]
    result=rank(samples,ws,["complete","incomplete"],ScoringConfig().weights,markets)
    assert result[0]["exchange_id"] == "complete"
    assert result[1]["confidence"] == "INSUFFICIENT"


def test_websocket_instability_penalizes_bad_events_and_disconnects():
    samples=[sample(ex,x) for ex in ("stable","unstable") for x in range(10,30)]
    ws=[]; markets=[]
    for ex in ("stable","unstable"):
        for symbol in ("BTCUSDT","ETHUSDT","SOLUSDT"):
            ws.append({"exchange_id":ex,"symbol":symbol,"success":True,"first_message_ms":50,"p95_interval_ms":10,"messages":100,"disconnects":0 if ex=="stable" else 2,"sequence_gaps":0 if ex=="stable" else 20})
            markets.append({"exchange_id":ex,"symbol":symbol,"success":True,"spread_bps":1,"bid_depth_10bps":100,"ask_depth_10bps":100,"quote_volume_24h":1000,"trade_frequency_hz":10,"futures_market_count":10})
    result={row["exchange_id"]:row for row in rank(samples,ws,["stable","unstable"],ScoringConfig().weights,markets)}
    assert result["stable"]["components"]["websocket"] > result["unstable"]["components"]["websocket"]
    assert result["stable"]["raw_metrics"]["ws_instability"] < result["unstable"]["raw_metrics"]["ws_instability"]


def test_cross_window_inconsistency_prevents_high_confidence():
    samples=[]
    for window,value in enumerate((10,10,10,100,100,100)):
        run_id=f"run{window}"
        samples.extend(sample("venue",value,run_id=run_id) for _ in range(20))
        samples.append({"run_id":run_id,"exchange_id":"venue","probe_type":"tcp","endpoint":"wss://example.test","duration_ms":10,"success":True})
    ws=[{"exchange_id":"venue","symbol":symbol,"success":True,"first_message_ms":50,"p95_interval_ms":10,"disconnects":0,"messages":100,"timestamp_quality":"VERIFIED","observation_seconds":600} for symbol in ("BTCUSDT","ETHUSDT","SOLUSDT")]
    markets=[{"exchange_id":"venue","symbol":symbol,"success":True,"spread_bps":1,"bid_depth_10bps":100,"ask_depth_10bps":100,"quote_volume_24h":1000,"trade_frequency_hz":10,"futures_market_count":10} for symbol in ("BTCUSDT","ETHUSDT","SOLUSDT")]
    row=rank(samples,ws,["venue"],ScoringConfig().weights,markets,window_count=6)[0]
    assert row["raw_metrics"]["cross_window_rest_p95_cv"] > .5
    assert row["raw_metrics"]["ws_observation_seconds"] == 1800
    assert row["confidence"] == "LOW"


def test_behavior_labels_are_explicit_and_evidence_aware():
    assert _behavior_label("INSUFFICIENT", 100, 100) == "insufficient_evidence"
    assert _behavior_label("MEDIUM", 80, 20) == "fast_but_unstable"
    assert _behavior_label("MEDIUM", 20, 80) == "stable_but_slower"
    assert _behavior_label("MEDIUM", 20, 20) == "consistently_poor"
    assert _behavior_label("MEDIUM", 60, 60) == "balanced"


def test_latency_normalization_is_direction_aware_and_bounded():
    scores=_lower_is_better({"fast":10,"middle":20,"slow":30,"missing":None})
    assert scores["fast"] == 100
    assert 0 < scores["middle"] < 100
    assert scores["slow"] == 0
    assert scores["missing"] == 0


def test_timestamp_quality_preserves_measured_out_of_bounds_evidence():
    ws=[{"exchange_id":"venue","symbol":symbol,"success":True,"messages":1,"timestamp_quality":"MEASURED_OFFSET_OUT_OF_BOUNDS"} for symbol in ("BTCUSDT","ETHUSDT","SOLUSDT")]
    row=rank([],ws,["venue"],ScoringConfig().weights)[0]
    assert row["raw_metrics"]["timestamp_quality"] == "MEASURED_OFFSET_OUT_OF_BOUNDS"
    assert row["raw_metrics"]["timestamp_quality_counts"] == {"MEASURED_OFFSET_OUT_OF_BOUNDS":3}
