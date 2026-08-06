from pathlib import Path

from cexlatency.cli import _generate_stored_report
from cexlatency.config import AppConfig, CampaignConfig, ProbeConfig
from cexlatency.models import OrderBookQuality, ProbeSample, WebSocketSummary, utc_now
from cexlatency.storage import Storage
from cexlatency.validation import NOT_READY_GATE, READY_GATE, audit_campaign_acceptance


def test_acceptance_fails_closed_without_campaign_evidence(tmp_path):
    config=AppConfig(storage_path=str(tmp_path/"db.sqlite"),report_directory=str(tmp_path/"reports"))
    with Storage(config.storage_path) as store: result=audit_campaign_acceptance(store,config,config.campaign.name)
    assert result["gate"] == NOT_READY_GATE
    assert not result["ready"]
    assert "all_windows_completed" in result["failed_checks"]


def test_acceptance_ready_requires_complete_normalized_evidence_and_reports(tmp_path):
    config=AppConfig(
        campaign=CampaignConfig(name="acceptance",duration_days=1,windows_local=["00:00"]),
        probes=ProbeConfig(iterations=2,websocket_observation_seconds=1),
        storage_path=str(tmp_path/"db.sqlite"),
        report_directory=str(tmp_path/"reports"),
    )
    run_id="complete-run"
    with Storage(config.storage_path) as store:
        store.start_run(run_id,config.model_dump(),"host","1.0","git-sha")
        for exchange in config.selected_exchanges():
            for probe_type in ("rest_reuse","rest_fresh"):
                for _ in range(2): store.add_sample(ProbeSample(run_id,exchange,probe_type,"https://example.test",True,utc_now(),duration_ms=10))
            store.add_sample(ProbeSample(run_id,exchange,"tcp","wss://example.test",True,utc_now(),duration_ms=5,tcp_ms=5))
            for symbol in config.benchmark_symbols():
                store.add_websocket(WebSocketSummary(run_id,exchange,"wss://example.test",symbol,True,first_message_ms=20,p95_interval_ms=10,messages=10,timestamp_quality="VERIFIED",observation_seconds=1))
                store.add_orderbook(OrderBookQuality(run_id,exchange,symbol,symbol,True,utc_now(),spread_bps=1,bid_depth_10bps=100,ask_depth_10bps=100,quote_volume_24h=1000,trade_frequency_hz=5,futures_market_count=100))
        store.finish_run(run_id)
        store.ensure_campaign_windows("acceptance",[("2026-01-01T00:00:00+00:00","2026-01-01T02:00:00+02:00")])
        store.finish_campaign_window("acceptance","2026-01-01T00:00:00+00:00",run_id)
    report_id,paths=_generate_stored_report(config,campaign_name="acceptance")
    assert report_id == "campaign-acceptance"
    assert all(Path(path).is_file() for path in paths.values())
    with Storage(config.storage_path) as store: result=audit_campaign_acceptance(store,config,"acceptance")
    assert result["gate"] == READY_GATE
    assert result["ready"]
    assert not result["failed_checks"]
