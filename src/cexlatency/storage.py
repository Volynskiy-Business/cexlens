from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .models import ProbeSample, WebSocketSummary, utc_now


SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS benchmark_runs (run_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, ended_at TEXT, status TEXT NOT NULL, config_json TEXT NOT NULL, host_id TEXT, version TEXT, git_sha TEXT);
CREATE TABLE IF NOT EXISTS hosts (host_id TEXT PRIMARY KEY, hostname_hash TEXT, os_version TEXT, python_version TEXT, timezone TEXT, public_ip_hash TEXT);
CREATE TABLE IF NOT EXISTS exchanges (exchange_id TEXT PRIMARY KEY, display_name TEXT NOT NULL, adapter_version TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS endpoints (id INTEGER PRIMARY KEY, exchange_id TEXT NOT NULL, kind TEXT NOT NULL, url TEXT NOT NULL, observed_at TEXT NOT NULL, UNIQUE(exchange_id, kind, url));
CREATE TABLE IF NOT EXISTS markets (id INTEGER PRIMARY KEY, exchange_id TEXT NOT NULL, canonical_symbol TEXT NOT NULL, native_symbol TEXT NOT NULL, market_type TEXT NOT NULL, UNIQUE(exchange_id, canonical_symbol));
CREATE TABLE IF NOT EXISTS probe_samples (id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, exchange_id TEXT NOT NULL, probe_type TEXT NOT NULL, endpoint TEXT NOT NULL, success INTEGER NOT NULL, started_at TEXT NOT NULL, duration_ms REAL, dns_ms REAL, tcp_ms REAL, tls_ms REAL, ttfb_ms REAL, status_code INTEGER, payload_bytes INTEGER, resolved_ip TEXT, address_family TEXT, error_class TEXT, error_detail TEXT, metadata_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS websocket_sessions (id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, exchange_id TEXT NOT NULL, endpoint TEXT NOT NULL, symbol TEXT NOT NULL, success INTEGER NOT NULL, summary_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS websocket_events_summary (id INTEGER PRIMARY KEY, session_id INTEGER, metric_json TEXT);
CREATE TABLE IF NOT EXISTS orderbook_quality_summary (id INTEGER PRIMARY KEY, run_id TEXT, exchange_id TEXT, symbol TEXT, summary_json TEXT);
CREATE TABLE IF NOT EXISTS route_diagnostics (id INTEGER PRIMARY KEY, run_id TEXT, exchange_id TEXT, endpoint TEXT, captured_at TEXT, output TEXT);
CREATE TABLE IF NOT EXISTS exchange_capabilities (exchange_id TEXT PRIMARY KEY, capabilities_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS score_snapshots (id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, exchange_id TEXT NOT NULL, overall_score REAL, confidence TEXT NOT NULL, components_json TEXT NOT NULL, raw_metrics_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS report_artifacts (id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, kind TEXT NOT NULL, path TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS errors (id INTEGER PRIMARY KEY, run_id TEXT, exchange_id TEXT, endpoint TEXT, probe_type TEXT, timestamp TEXT, exception_type TEXT, retry_number INTEGER, classification TEXT, recoverable INTEGER, detail TEXT);
"""


class Storage:
    def __init__(self, path: str | Path):
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)

    def close(self) -> None: self.connection.close()
    def __enter__(self) -> "Storage": return self
    def __exit__(self, *_: object) -> None: self.close()

    def start_run(self, run_id: str, config: dict[str, Any], host_id: str, version: str, git_sha: str | None) -> None:
        self.connection.execute("INSERT INTO benchmark_runs VALUES (?, ?, NULL, 'RUNNING', ?, ?, ?, ?)", (run_id, utc_now(), json.dumps(config), host_id, version, git_sha)); self.connection.commit()

    def finish_run(self, run_id: str, status: str = "COMPLETED") -> None:
        self.connection.execute("UPDATE benchmark_runs SET ended_at=?, status=? WHERE run_id=?", (utc_now(), status, run_id)); self.connection.commit()

    def add_sample(self, s: ProbeSample) -> None:
        d=s.to_dict(); metadata=json.dumps(d.pop("metadata")); cols=", ".join(d); marks=", ".join("?" for _ in d)
        self.connection.execute(f"INSERT INTO probe_samples ({cols}, metadata_json) VALUES ({marks}, ?)", (*[int(v) if isinstance(v,bool) else v for v in d.values()], metadata)); self.connection.commit()
        if not s.success: self._add_error(s.run_id,s.exchange_id,s.endpoint,s.probe_type,s.error_class,s.error_detail)

    def add_websocket(self, s: WebSocketSummary) -> None:
        self.connection.execute("INSERT INTO websocket_sessions (run_id,exchange_id,endpoint,symbol,success,summary_json) VALUES (?,?,?,?,?,?)", (s.run_id,s.exchange_id,s.endpoint,s.symbol,int(s.success),json.dumps(s.to_dict()))); self.connection.commit()
        if not s.success: self._add_error(s.run_id,s.exchange_id,s.endpoint,"websocket",s.error_class,s.error_detail)

    def _add_error(self, run_id: str, exchange: str, endpoint: str, probe: str, classification: str | None, detail: str | None) -> None:
        self.connection.execute("INSERT INTO errors (run_id,exchange_id,endpoint,probe_type,timestamp,exception_type,retry_number,classification,recoverable,detail) VALUES (?,?,?,?,?,?,?,?,?,?)",(run_id,exchange,endpoint,probe,utc_now(),classification,0,classification,1,detail)); self.connection.commit()

    def samples(self, run_id: str) -> list[dict[str, Any]]:
        return [dict(r) for r in self.connection.execute("SELECT * FROM probe_samples WHERE run_id=? ORDER BY id", (run_id,))]

    def websockets(self, run_id: str) -> list[dict[str, Any]]:
        rows=[]
        for r in self.connection.execute("SELECT summary_json FROM websocket_sessions WHERE run_id=?",(run_id,)): rows.append(json.loads(r[0]))
        return rows

    def save_score(self, run_id: str, row: dict[str, Any]) -> None:
        self.connection.execute("INSERT INTO score_snapshots (run_id,exchange_id,overall_score,confidence,components_json,raw_metrics_json) VALUES (?,?,?,?,?,?)",(run_id,row["exchange_id"],row.get("overall_score"),row["confidence"],json.dumps(row["components"]),json.dumps(row["raw_metrics"]))); self.connection.commit()

    def latest_run_id(self) -> str | None:
        row=self.connection.execute("SELECT run_id FROM benchmark_runs ORDER BY started_at DESC LIMIT 1").fetchone(); return row[0] if row else None

    def add_report(self, run_id: str, kind: str, path: str) -> None:
        self.connection.execute("INSERT INTO report_artifacts (run_id,kind,path,created_at) VALUES (?,?,?,?)",(run_id,kind,path,utc_now())); self.connection.commit()

