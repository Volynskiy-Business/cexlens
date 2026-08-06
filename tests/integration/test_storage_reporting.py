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
    paths = generate_reports("run1", rankings, samples, tmp_path / "reports")
    assert set(paths) == {"html", "markdown", "json", "rankings_csv", "samples_csv", "websockets_csv", "market_quality_csv"}
    assert all((tmp_path / "reports" / "run1" / name).exists() for name in ("dashboard.html", "executive-report.md", "summary.json", "rankings.csv", "probe_samples.csv", "websocket_sessions.csv", "market_quality.csv"))
    assert json.loads((tmp_path / "reports" / "run1" / "summary.json").read_text())["recommendation"] == "binance"


def test_campaign_window_claim_completion_and_resume(tmp_path):
    with Storage(tmp_path / "campaign.db") as store:
        store.ensure_campaign_windows("c", [("2026-01-01T00:00:00+00:00", "2026-01-01T02:00:00+02:00"), ("2026-01-02T00:00:00+00:00", "2026-01-02T02:00:00+02:00")])
        due = store.due_campaign_windows("c", "2026-01-01T01:00:00+00:00")
        assert len(due) == 1
        assert store.claim_campaign_window("c", due[0]["window_utc"])
        assert not store.claim_campaign_window("c", due[0]["window_utc"])
        assert store.resume_campaign("c") == 1
        assert store.claim_campaign_window("c", due[0]["window_utc"])
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
