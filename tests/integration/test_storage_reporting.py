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
    assert set(paths) == {"html", "markdown", "json", "rankings_csv", "samples_csv"}
    assert all((tmp_path / "reports" / "run1" / name).exists() for name in ("dashboard.html", "executive-report.md", "summary.json", "rankings.csv", "probe_samples.csv"))
    assert json.loads((tmp_path / "reports" / "run1" / "summary.json").read_text())["recommendation"] == "binance"

