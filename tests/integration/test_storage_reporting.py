import json

from cexlatency.models import ProbeSample, utc_now
from cexlatency.reporting import generate_reports
from cexlatency.storage import Storage


def test_sqlite_round_trip_and_all_report_formats(tmp_path):
    db = tmp_path / "test.db"
    with Storage(db) as store:
        store.start_run("run1", {}, "host", "0.1", None)
        store.add_sample(ProbeSample("run1", "binance", "rest_reuse", "https://example.test", True, utc_now(), duration_ms=42, status_code=200))
        store.finish_run("run1")
        samples = store.samples("run1")
    rankings = [{"exchange_id": "binance", "overall_score": 80.0, "confidence": "MEDIUM", "evidence_coverage": 1.0, "components": {}, "raw_metrics": {"rest_median": 42, "rest_p95": 42, "rest_p99": 42}}]
    paths = generate_reports("run1", rankings, samples, tmp_path / "reports", timezone_name="Asia/Jerusalem")
    assert set(paths) == {"html", "markdown", "json", "rankings_csv", "samples_csv", "websockets_csv", "market_quality_csv", "statistics_csv"}
    assert all((tmp_path / "reports" / "run1" / name).exists() for name in ("dashboard.html", "executive-report.md", "summary.json", "rankings.csv", "probe_samples.csv", "websocket_sessions.csv", "market_quality.csv", "metric_statistics.csv"))
    summary=json.loads((tmp_path / "reports" / "run1" / "summary.json").read_text())
    assert summary["recommendation"] == "binance"
    assert summary["recommendations"]["winner_rationale"]["confidence"] == "MEDIUM"
    assert summary["recommendations"]["details"]["best_low_latency"]["reason"].startswith("lowest measured REST p95")
    assert summary["timezone"] == "Asia/Jerusalem"
    assert summary["probe_and_session_statistics"][0]["metric"] == "total_duration_ms"
    dashboard=(tmp_path / "reports" / "run1" / "dashboard.html").read_text(encoding="utf-8")
    assert "Asia/Jerusalem" in dashboard
    assert "metadata_json" in (tmp_path / "reports" / "run1" / "probe_samples.csv").read_text(encoding="utf-8").splitlines()[0]
    for section in ("Executive Overview","Exchange Ranking","Latency Distribution","Tail Latency","WebSocket Stability","Time-of-Day Comparison","Route Diagnostics","Order-Book Quality","Futures Coverage","Raw Evidence","Methodology","Limitations","Jitter Over Time","Reconnect Duration"):
        assert section in dashboard


def test_structured_route_round_trip(tmp_path):
    with Storage(tmp_path/"routes.db") as store:
        store.add_route("run","binance","https://example.test","raw",{"hop_count":3,"route_fingerprint":"abc"})
        routes=store.routes("run")
    assert routes[0]["summary"] == {"hop_count":3,"route_fingerprint":"abc"}


def test_explicit_clock_quality_error_is_persisted(tmp_path):
    with Storage(tmp_path/"errors.db") as store:
        store.add_error("run","__host__","local-clock","clock","CLOCK_QUALITY_UNKNOWN","offset unavailable")
        row=store.connection.execute("SELECT classification,recoverable,detail FROM errors").fetchone()
    assert tuple(row) == ("CLOCK_QUALITY_UNKNOWN",1,"offset unavailable")


def test_retention_prunes_only_unreferenced_old_runs(tmp_path):
    with Storage(tmp_path/"retention.db") as store:
        for run_id in ("old","campaign-old","new"):
            store.start_run(run_id,{},"host","1",None); store.finish_run(run_id)
        store.connection.execute("UPDATE benchmark_runs SET ended_at='2020-01-01T00:00:00+00:00' WHERE run_id IN ('old','campaign-old')")
        store.connection.execute("UPDATE benchmark_runs SET ended_at='2026-01-01T00:00:00+00:00' WHERE run_id='new'")
        store.ensure_campaign_windows("campaign",[("2020-01-01T00:00:00+00:00","local")])
        store.finish_campaign_window("campaign","2020-01-01T00:00:00+00:00","campaign-old")
        assert store.retention_candidates("2025-01-01T00:00:00+00:00") == ["old"]
        assert store.prune_runs_before("2025-01-01T00:00:00+00:00") == ["old"]
        remaining={row[0] for row in store.connection.execute("SELECT run_id FROM benchmark_runs")}
    assert remaining == {"campaign-old","new"}


def test_campaign_window_claim_completion_and_resume(tmp_path):
    with Storage(tmp_path / "campaign.db") as store:
        store.ensure_campaign_windows("c", [("2026-01-01T00:00:00+00:00", "2026-01-01T02:00:00+02:00"), ("2026-01-02T00:00:00+00:00", "2026-01-02T02:00:00+02:00")])
        due = store.due_campaign_windows("c", "2026-01-01T01:00:00+00:00")
        assert len(due) == 1
        assert store.claim_campaign_window("c", due[0]["window_utc"],"worker","2026-01-01T03:00:00+00:00")
        assert not store.claim_campaign_window("c", due[0]["window_utc"])
        assert store.resume_campaign("c","2026-01-01T01:00:00+00:00","2025-12-31T22:00:00+00:00") == 0
        assert store.resume_campaign("c","2026-01-01T04:00:00+00:00","2026-01-01T01:00:00+00:00") == 1
        assert store.claim_campaign_window("c", due[0]["window_utc"],"worker2","2026-01-01T06:00:00+00:00")
        store.finish_campaign_window("c", due[0]["window_utc"], "run42")
        assert store.campaign_summary("c")["COMPLETED"] == 1
        assert store.campaign_run_ids("c") == ["run42"]
        assert store.campaign_window_count("c") == 2
        assert store.campaign_windows("c")[0]["run_id"] == "run42"


def test_schema_migration_adds_reproducibility_metadata(tmp_path):
    db=tmp_path/"legacy.db"
    import sqlite3
    conn=sqlite3.connect(db); conn.execute("CREATE TABLE hosts (host_id TEXT PRIMARY KEY, hostname_hash TEXT, os_version TEXT, python_version TEXT, timezone TEXT, public_ip_hash TEXT)"); conn.commit(); conn.close()
    with Storage(db) as store:
        columns={row[1] for row in store.connection.execute("PRAGMA table_info(hosts)")}
    assert {"network_interface","isp_name"} <= columns


def test_campaign_definition_is_immutable_and_old_windows_expire(tmp_path):
    import pytest
    with Storage(tmp_path/"campaign.db") as store:
        store.ensure_campaign_definition("c","hash1",{"version":1})
        store.ensure_campaign_definition("c","hash1",{"version":1})
        assert store.campaign_definition("c") == {"version":1}
        with pytest.raises(ValueError,match="CONFIGURATION_ERROR"):
            store.ensure_campaign_definition("c","hash2",{"version":2})
        store.ensure_campaign_windows("c",[("2026-01-01T00:00:00+00:00","local")])
        assert store.expire_campaign_windows("c","2026-01-01T01:00:00+00:00") == 1
        assert store.campaign_summary("c")["MISSED"] == 1
