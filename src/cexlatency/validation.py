from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .adapters import REGISTRY
from .config import AppConfig
from .storage import Storage


READY_GATE = "CEX_LATENCY_PLATFORM_MVP_READY"
NOT_READY_GATE = "CEX_LATENCY_PLATFORM_MVP_NOT_READY"


def audit_campaign_acceptance(store: Storage, config: AppConfig, campaign_name: str) -> dict[str, Any]:
    exchanges=config.selected_exchanges("priority")
    symbols=config.benchmark_symbols()
    expected_windows=config.campaign.duration_days*len(config.campaign.windows_local)
    summary=store.campaign_summary(campaign_name)
    run_ids=store.campaign_run_ids(campaign_name)
    checks: dict[str,bool]={
        "at_least_10_registered_exchanges": len(exchanges)>=10 and all(exchange in REGISTRY for exchange in exchanges),
        "at_least_3_futures_symbols": len(symbols)>=3,
        "expected_window_count": store.campaign_window_count(campaign_name)==expected_windows,
        "all_windows_completed": summary["COMPLETED"]==expected_windows and all(summary[state]==0 for state in ("PENDING","RUNNING","FAILED","MISSED")),
        "unique_run_per_window": len(run_ids)==expected_windows and len(set(run_ids))==expected_windows,
    }
    completed_runs=0
    reproducible_runs=0
    rest_complete=True
    websocket_complete=True
    market_complete=True
    for run_id in run_ids:
        run=store.connection.execute("SELECT status,config_json,host_id,version,git_sha,started_at,ended_at FROM benchmark_runs WHERE run_id=?",(run_id,)).fetchone()
        if run and run["status"]=="COMPLETED": completed_runs+=1
        if run and all(run[key] not in (None,"") for key in ("config_json","host_id","version","git_sha","started_at","ended_at")): reproducible_runs+=1
        for exchange in exchanges:
            for probe_type in ("rest_reuse","rest_fresh"):
                count=store.connection.execute("SELECT count(*) FROM probe_samples WHERE run_id=? AND exchange_id=? AND probe_type=?",(run_id,exchange,probe_type)).fetchone()[0]
                rest_complete &= count>=config.probes.iterations
            ws_symbols={row[0] for row in store.connection.execute("SELECT symbol FROM websocket_sessions WHERE run_id=? AND exchange_id=?",(run_id,exchange))}
            market_symbols={row[0] for row in store.connection.execute("SELECT symbol FROM orderbook_quality_summary WHERE run_id=? AND exchange_id=?",(run_id,exchange))}
            websocket_complete &= set(symbols)<=ws_symbols
            market_complete &= set(symbols)<=market_symbols
    checks.update({
        "all_runs_completed": completed_runs==expected_windows,
        "reproducibility_metadata_complete": reproducible_runs==expected_windows,
        "rest_fresh_and_reuse_coverage": bool(run_ids) and rest_complete,
        "websocket_symbol_coverage": bool(run_ids) and websocket_complete,
        "market_quality_symbol_coverage": bool(run_ids) and market_complete,
    })
    report_id="campaign-"+"".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in campaign_name)
    report_root=Path(config.report_directory)/report_id
    required_reports=("dashboard.html","executive-report.md","summary.json","rankings.csv","probe_samples.csv","websocket_sessions.csv","market_quality.csv","metric_statistics.csv")
    checks["aggregate_report_complete"]=all((report_root/name).is_file() for name in required_reports)
    recommendation=None
    try:
        recommendation=json.loads((report_root/"summary.json").read_text(encoding="utf-8")).get("recommendation")
    except (OSError,json.JSONDecodeError):
        pass
    checks["eligible_recommendation_declared"]=bool(recommendation)
    ready=all(checks.values())
    return {
        "campaign":campaign_name,
        "gate":READY_GATE if ready else NOT_READY_GATE,
        "ready":ready,
        "expected_windows":expected_windows,
        "campaign_summary":summary,
        "completed_run_ids":run_ids,
        "recommendation":recommendation,
        "checks":checks,
        "failed_checks":[name for name,passed in checks.items() if not passed],
    }
