from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .models import ClockStatus, OrderBookQuality, ProbeSample, WebSocketSummary, utc_now


SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS benchmark_runs (run_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, ended_at TEXT, status TEXT NOT NULL, config_json TEXT NOT NULL, host_id TEXT, version TEXT, git_sha TEXT);
CREATE TABLE IF NOT EXISTS hosts (host_id TEXT PRIMARY KEY, hostname_hash TEXT, os_version TEXT, python_version TEXT, timezone TEXT, public_ip_hash TEXT, network_interface TEXT, isp_name TEXT);
CREATE TABLE IF NOT EXISTS exchanges (exchange_id TEXT PRIMARY KEY, display_name TEXT NOT NULL, adapter_version TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS endpoints (id INTEGER PRIMARY KEY, exchange_id TEXT NOT NULL, kind TEXT NOT NULL, url TEXT NOT NULL, observed_at TEXT NOT NULL, UNIQUE(exchange_id, kind, url));
CREATE TABLE IF NOT EXISTS markets (id INTEGER PRIMARY KEY, exchange_id TEXT NOT NULL, canonical_symbol TEXT NOT NULL, native_symbol TEXT NOT NULL, market_type TEXT NOT NULL, UNIQUE(exchange_id, canonical_symbol));
CREATE TABLE IF NOT EXISTS probe_samples (id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, exchange_id TEXT NOT NULL, probe_type TEXT NOT NULL, endpoint TEXT NOT NULL, success INTEGER NOT NULL, started_at TEXT NOT NULL, duration_ms REAL, dns_ms REAL, tcp_ms REAL, tls_ms REAL, ttfb_ms REAL, status_code INTEGER, payload_bytes INTEGER, resolved_ip TEXT, address_family TEXT, error_class TEXT, error_detail TEXT, metadata_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS websocket_sessions (id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, exchange_id TEXT NOT NULL, endpoint TEXT NOT NULL, symbol TEXT NOT NULL, success INTEGER NOT NULL, summary_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS websocket_events_summary (id INTEGER PRIMARY KEY, session_id INTEGER, metric_json TEXT);
CREATE TABLE IF NOT EXISTS orderbook_quality_summary (id INTEGER PRIMARY KEY, run_id TEXT, exchange_id TEXT, symbol TEXT, summary_json TEXT);
CREATE TABLE IF NOT EXISTS route_diagnostics (id INTEGER PRIMARY KEY, run_id TEXT, exchange_id TEXT, endpoint TEXT, captured_at TEXT, output TEXT, summary_json TEXT);
CREATE TABLE IF NOT EXISTS exchange_capabilities (exchange_id TEXT PRIMARY KEY, capabilities_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS score_snapshots (id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, exchange_id TEXT NOT NULL, overall_score REAL, confidence TEXT NOT NULL, behavior_label TEXT, components_json TEXT NOT NULL, raw_metrics_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS report_artifacts (id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, kind TEXT NOT NULL, path TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS errors (id INTEGER PRIMARY KEY, run_id TEXT, exchange_id TEXT, endpoint TEXT, probe_type TEXT, timestamp TEXT, exception_type TEXT, retry_number INTEGER, classification TEXT, recoverable INTEGER, detail TEXT);
CREATE TABLE IF NOT EXISTS campaign_windows (campaign_name TEXT NOT NULL, window_utc TEXT NOT NULL, local_label TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING', run_id TEXT, attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT, updated_at TEXT NOT NULL, claimed_by TEXT, lease_expires_at TEXT, PRIMARY KEY(campaign_name, window_utc));
CREATE TABLE IF NOT EXISTS campaign_definitions (campaign_name TEXT PRIMARY KEY, definition_hash TEXT NOT NULL, config_json TEXT NOT NULL, created_at TEXT NOT NULL);
"""


class Storage:
    def __init__(self, path: str | Path):
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)
        self._ensure_column("hosts","network_interface","TEXT")
        self._ensure_column("hosts","isp_name","TEXT")
        self._ensure_column("campaign_windows","claimed_by","TEXT")
        self._ensure_column("campaign_windows","lease_expires_at","TEXT")
        self._ensure_column("route_diagnostics","summary_json","TEXT")
        self._ensure_column("score_snapshots","behavior_label","TEXT")

    def _ensure_column(self, table: str, column: str, declaration: str) -> None:
        columns={row[1] for row in self.connection.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")
            self.connection.commit()

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

    def add_orderbook(self, s: OrderBookQuality) -> None:
        self.connection.execute(
            "INSERT INTO orderbook_quality_summary (run_id,exchange_id,symbol,summary_json) VALUES (?,?,?,?)",
            (s.run_id, s.exchange_id, s.symbol, json.dumps(s.to_dict())),
        )
        self.connection.commit()
        if not s.success:
            self._add_error(s.run_id, s.exchange_id, "", "orderbook", s.error_class, s.error_detail)

    def orderbooks(self, run_id: str) -> list[dict[str, Any]]:
        return [json.loads(r[0]) for r in self.connection.execute("SELECT summary_json FROM orderbook_quality_summary WHERE run_id=?", (run_id,))]

    def add_route(self, run_id: str, exchange_id: str, endpoint: str, output: str, summary: dict[str,Any] | None = None) -> None:
        self.connection.execute("INSERT INTO route_diagnostics (run_id,exchange_id,endpoint,captured_at,output,summary_json) VALUES (?,?,?,?,?,?)", (run_id,exchange_id,endpoint,utc_now(),output,json.dumps(summary or {})))
        self.connection.commit()

    def routes(self, run_id: str) -> list[dict[str, Any]]:
        rows=[]
        for row in self.connection.execute("SELECT exchange_id,endpoint,captured_at,output,summary_json FROM route_diagnostics WHERE run_id=? ORDER BY exchange_id", (run_id,)):
            item=dict(row); item["summary"]=json.loads(item.pop("summary_json") or "{}"); rows.append(item)
        return rows

    def upsert_host(self, host_id: str, hostname_hash: str, os_version: str, python_version: str, timezone: str, clock: ClockStatus, network: dict[str, str | None] | None = None) -> None:
        network=network or {}
        self.connection.execute(
            "INSERT INTO hosts (host_id,hostname_hash,os_version,python_version,timezone,public_ip_hash,network_interface,isp_name) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(host_id) DO UPDATE SET os_version=excluded.os_version,python_version=excluded.python_version,timezone=excluded.timezone,public_ip_hash=excluded.public_ip_hash,network_interface=excluded.network_interface,isp_name=excluded.isp_name",
            (host_id,hostname_hash,os_version,python_version,timezone,network.get("public_ip_hash"),network.get("network_interface"),network.get("isp_name")),
        )
        self.connection.execute("INSERT OR REPLACE INTO exchange_capabilities (exchange_id,capabilities_json) VALUES (?,?)", (f"__clock__:{host_id}", json.dumps(clock.to_dict())))
        self.connection.commit()

    def register_adapter(self, exchange_id: str, display_name: str, adapter_version: str, endpoints: list[Any], markets: list[Any], capabilities: dict[str, Any]) -> None:
        self.connection.execute("INSERT INTO exchanges (exchange_id,display_name,adapter_version) VALUES (?,?,?) ON CONFLICT(exchange_id) DO UPDATE SET display_name=excluded.display_name,adapter_version=excluded.adapter_version", (exchange_id,display_name,adapter_version))
        self.connection.executemany("INSERT OR IGNORE INTO endpoints (exchange_id,kind,url,observed_at) VALUES (?,?,?,?)", [(e.exchange_id,e.kind,e.url,utc_now()) for e in endpoints])
        self.connection.executemany("INSERT OR IGNORE INTO markets (exchange_id,canonical_symbol,native_symbol,market_type) VALUES (?,?,?,?)", [(m.exchange_id,m.canonical_symbol,m.native_symbol,m.market_type) for m in markets])
        self.connection.execute("INSERT INTO exchange_capabilities (exchange_id,capabilities_json) VALUES (?,?) ON CONFLICT(exchange_id) DO UPDATE SET capabilities_json=excluded.capabilities_json",(exchange_id,json.dumps(capabilities)))
        self.connection.commit()

    def _add_error(self, run_id: str, exchange: str, endpoint: str, probe: str, classification: str | None, detail: str | None) -> None:
        self.connection.execute("INSERT INTO errors (run_id,exchange_id,endpoint,probe_type,timestamp,exception_type,retry_number,classification,recoverable,detail) VALUES (?,?,?,?,?,?,?,?,?,?)",(run_id,exchange,endpoint,probe,utc_now(),classification,0,classification,1,detail)); self.connection.commit()

    def samples(self, run_id: str) -> list[dict[str, Any]]:
        return [dict(r) for r in self.connection.execute("SELECT * FROM probe_samples WHERE run_id=? ORDER BY id", (run_id,))]

    def websockets(self, run_id: str) -> list[dict[str, Any]]:
        rows=[]
        for r in self.connection.execute("SELECT summary_json FROM websocket_sessions WHERE run_id=?",(run_id,)): rows.append(json.loads(r[0]))
        return rows

    def save_score(self, run_id: str, row: dict[str, Any]) -> None:
        self.connection.execute("INSERT INTO score_snapshots (run_id,exchange_id,overall_score,confidence,behavior_label,components_json,raw_metrics_json) VALUES (?,?,?,?,?,?,?)",(run_id,row["exchange_id"],row.get("overall_score"),row["confidence"],row.get("behavior_label"),json.dumps(row["components"]),json.dumps(row["raw_metrics"]))); self.connection.commit()

    def latest_run_id(self) -> str | None:
        row=self.connection.execute("SELECT run_id FROM benchmark_runs ORDER BY started_at DESC LIMIT 1").fetchone(); return row[0] if row else None

    def add_report(self, run_id: str, kind: str, path: str) -> None:
        self.connection.execute("INSERT INTO report_artifacts (run_id,kind,path,created_at) VALUES (?,?,?,?)",(run_id,kind,path,utc_now())); self.connection.commit()

    def ensure_campaign_windows(self, campaign_name: str, windows: list[tuple[str, str]]) -> None:
        self.connection.executemany(
            "INSERT OR IGNORE INTO campaign_windows (campaign_name,window_utc,local_label,status,updated_at) VALUES (?,?,?,'PENDING',?)",
            [(campaign_name, utc, local, utc_now()) for utc, local in windows],
        )
        self.connection.commit()

    def ensure_campaign_definition(self, campaign_name: str, definition_hash: str, config: dict[str, Any]) -> None:
        row=self.connection.execute("SELECT definition_hash FROM campaign_definitions WHERE campaign_name=?",(campaign_name,)).fetchone()
        if row and row[0] != definition_hash:
            raise ValueError(f"CONFIGURATION_ERROR: campaign {campaign_name!r} already exists with a different immutable definition")
        self.connection.execute("INSERT OR IGNORE INTO campaign_definitions (campaign_name,definition_hash,config_json,created_at) VALUES (?,?,?,?)",(campaign_name,definition_hash,json.dumps(config,sort_keys=True),utc_now()))
        self.connection.commit()

    def campaign_definition(self, campaign_name: str) -> dict[str, Any] | None:
        row=self.connection.execute("SELECT config_json FROM campaign_definitions WHERE campaign_name=?",(campaign_name,)).fetchone()
        return json.loads(row[0]) if row else None

    def campaign_window_count(self, campaign_name: str) -> int:
        return int(self.connection.execute("SELECT count(*) FROM campaign_windows WHERE campaign_name=?",(campaign_name,)).fetchone()[0])

    def resume_campaign(self, campaign_name: str, now_utc: str, legacy_stale_before_utc: str) -> int:
        cursor = self.connection.execute("UPDATE campaign_windows SET status='PENDING',claimed_by=NULL,lease_expires_at=NULL,last_error='Recovered after expired campaign lease',updated_at=? WHERE campaign_name=? AND status='RUNNING' AND ((lease_expires_at IS NOT NULL AND lease_expires_at<?) OR (lease_expires_at IS NULL AND updated_at<?))", (utc_now(),campaign_name,now_utc,legacy_stale_before_utc))
        self.connection.commit()
        return cursor.rowcount

    def expire_campaign_windows(self, campaign_name: str, cutoff_utc: str) -> int:
        cursor=self.connection.execute("UPDATE campaign_windows SET status='MISSED',last_error='Window grace period elapsed before claim',updated_at=? WHERE campaign_name=? AND status='PENDING' AND window_utc<?",(utc_now(),campaign_name,cutoff_utc))
        self.connection.commit()
        return cursor.rowcount

    def due_campaign_windows(self, campaign_name: str, now_utc: str, limit: int = 1) -> list[dict[str, Any]]:
        return [dict(r) for r in self.connection.execute("SELECT * FROM campaign_windows WHERE campaign_name=? AND status='PENDING' AND window_utc<=? ORDER BY window_utc LIMIT ?", (campaign_name, now_utc, limit))]

    def claim_campaign_window(self, campaign_name: str, window_utc: str, claimed_by: str = "local", lease_expires_at: str | None = None) -> bool:
        cursor = self.connection.execute("UPDATE campaign_windows SET status='RUNNING',attempts=attempts+1,claimed_by=?,lease_expires_at=?,updated_at=? WHERE campaign_name=? AND window_utc=? AND status='PENDING'", (claimed_by,lease_expires_at,utc_now(),campaign_name,window_utc))
        self.connection.commit()
        return cursor.rowcount == 1

    def finish_campaign_window(self, campaign_name: str, window_utc: str, run_id: str | None, error: str | None = None) -> None:
        self.connection.execute("UPDATE campaign_windows SET status=?,run_id=?,last_error=?,claimed_by=NULL,lease_expires_at=NULL,updated_at=? WHERE campaign_name=? AND window_utc=?", ("FAILED" if error else "COMPLETED",run_id,error,utc_now(),campaign_name,window_utc))
        self.connection.commit()

    def campaign_summary(self, campaign_name: str) -> dict[str, int]:
        result = {"PENDING":0,"RUNNING":0,"COMPLETED":0,"FAILED":0,"MISSED":0}
        for status,count in self.connection.execute("SELECT status,count(*) FROM campaign_windows WHERE campaign_name=? GROUP BY status", (campaign_name,)):
            result[status]=count
        return result

    def next_campaign_window(self, campaign_name: str) -> str | None:
        row=self.connection.execute("SELECT min(window_utc) FROM campaign_windows WHERE campaign_name=? AND status='PENDING'",(campaign_name,)).fetchone()
        return row[0] if row and row[0] else None

    def campaign_run_ids(self, campaign_name: str) -> list[str]:
        return [r[0] for r in self.connection.execute("SELECT run_id FROM campaign_windows WHERE campaign_name=? AND status='COMPLETED' AND run_id IS NOT NULL ORDER BY window_utc",(campaign_name,))]

    def campaign_windows(self, campaign_name: str) -> list[dict[str, Any]]:
        return [dict(r) for r in self.connection.execute("SELECT window_utc,local_label,status,run_id,attempts,last_error,claimed_by,lease_expires_at,updated_at FROM campaign_windows WHERE campaign_name=? ORDER BY window_utc",(campaign_name,))]

    def samples_for_runs(self, run_ids: list[str]) -> list[dict[str, Any]]:
        return [sample for run_id in run_ids for sample in self.samples(run_id)]

    def websockets_for_runs(self, run_ids: list[str]) -> list[dict[str, Any]]:
        return [row for run_id in run_ids for row in self.websockets(run_id)]

    def orderbooks_for_runs(self, run_ids: list[str]) -> list[dict[str, Any]]:
        return [row for run_id in run_ids for row in self.orderbooks(run_id)]

    def routes_for_runs(self, run_ids: list[str]) -> list[dict[str, Any]]:
        return [row for run_id in run_ids for row in self.routes(run_id)]

    def retention_candidates(self, cutoff_utc: str) -> list[str]:
        return [row[0] for row in self.connection.execute("SELECT run_id FROM benchmark_runs b WHERE b.ended_at IS NOT NULL AND b.ended_at<? AND NOT EXISTS (SELECT 1 FROM campaign_windows c WHERE c.run_id=b.run_id) ORDER BY b.ended_at",(cutoff_utc,))]

    def prune_runs_before(self, cutoff_utc: str) -> list[str]:
        run_ids=self.retention_candidates(cutoff_utc)
        if not run_ids: return []
        marks=",".join("?" for _ in run_ids)
        with self.connection:
            self.connection.execute(f"DELETE FROM websocket_events_summary WHERE session_id IN (SELECT id FROM websocket_sessions WHERE run_id IN ({marks}))",run_ids)
            for table in ("probe_samples","websocket_sessions","orderbook_quality_summary","route_diagnostics","score_snapshots","report_artifacts","errors"):
                self.connection.execute(f"DELETE FROM {table} WHERE run_id IN ({marks})",run_ids)
            self.connection.execute(f"DELETE FROM benchmark_runs WHERE run_id IN ({marks})",run_ids)
        return run_ids
