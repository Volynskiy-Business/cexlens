from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo

from .config import AppConfig
from .models import utc_now
from .runner import benchmark
from .storage import Storage


def build_schedule(config: AppConfig, start_local_date: date | datetime | None = None) -> list[tuple[str, str]]:
    zone = ZoneInfo(config.campaign.timezone)
    if isinstance(start_local_date,datetime):
        start_date=start_local_date.astimezone(zone).date() if start_local_date.tzinfo else start_local_date.date()
    elif isinstance(start_local_date,date):
        start_date=start_local_date
    else:
        start_date=datetime.now(zone).date()
    rows: list[tuple[str, str]] = []
    for day_offset in range(config.campaign.duration_days):
        current_date = start_date + timedelta(days=day_offset)
        for hhmm in config.campaign.windows_local:
            hour, minute = map(int, hhmm.split(":"))
            local = datetime(current_date.year,current_date.month,current_date.day,hour,minute,tzinfo=zone)
            rows.append((local.astimezone(timezone.utc).isoformat(), local.isoformat()))
    return sorted(rows)


async def run_campaign(
    config: AppConfig,
    exchange_ids: list[str],
    iterations: int | None = None,
    ws_duration: int | None = None,
    max_windows: int = 1,
    daemon: bool = False,
    poll_seconds: int = 30,
    progress: Callable[[str], None] = print,
    start_local_date: date | None = None,
) -> dict[str, Any]:
    name = config.campaign.name
    completed_runs: list[str] = []
    with Storage(config.storage_path) as store:
        existing_definition=store.campaign_definition(name)
        if start_local_date is None and existing_definition:
            resolved_start_date=date.fromisoformat(existing_definition["resolved_start_date_local"])
        else:
            resolved_start_date=start_local_date or datetime.now(ZoneInfo(config.campaign.timezone)).date()
        definition=config.model_dump(mode="json"); definition["resolved_start_date_local"]=resolved_start_date.isoformat()
        definition_hash=hashlib.sha256(json.dumps(definition,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        store.ensure_campaign_definition(name,definition_hash,definition)
        if store.campaign_window_count(name)==0:
            store.ensure_campaign_windows(name, build_schedule(config,resolved_start_date))
        now=datetime.now(timezone.utc); legacy_stale_before=now-timedelta(minutes=config.campaign.window_lease_minutes)
        recovered = store.resume_campaign(name,now.isoformat(),legacy_stale_before.isoformat())
    if recovered: progress(f"Recovered {recovered} interrupted campaign window(s)")
    processed = 0
    while processed < max_windows:
        with Storage(config.storage_path) as store:
            cutoff=(datetime.now(timezone.utc)-timedelta(minutes=config.campaign.window_grace_minutes)).isoformat()
            expired=store.expire_campaign_windows(name,cutoff)
            if expired: progress(f"Marked {expired} campaign window(s) MISSED after grace period")
            due = store.due_campaign_windows(name, utc_now(), 1)
            summary = store.campaign_summary(name)
            next_window = store.next_campaign_window(name)
        if not due:
            if not daemon or next_window is None:
                return {"campaign":name,"processed":processed,"run_ids":completed_runs,"summary":summary,"next_window_utc":next_window}
            next_dt=datetime.fromisoformat(next_window)
            wait=max(1,min(poll_seconds,int((next_dt-datetime.now(timezone.utc)).total_seconds())))
            progress(f"No due window; next={next_window}; sleeping {wait}s")
            await asyncio.sleep(wait)
            continue
        window=due[0]
        claimant=uuid.uuid4().hex
        lease_expires=(datetime.now(timezone.utc)+timedelta(minutes=config.campaign.window_lease_minutes)).isoformat()
        with Storage(config.storage_path) as store:
            if not store.claim_campaign_window(name,window["window_utc"],claimant,lease_expires): continue
        progress(f"Campaign window {window['local_label']} started")
        run_id: str | None = None
        try:
            run_id, _, _ = await benchmark(config,exchange_ids,iterations,ws_duration,progress)
            with Storage(config.storage_path) as store: store.finish_campaign_window(name,window["window_utc"],run_id)
            completed_runs.append(run_id)
        except (KeyboardInterrupt,asyncio.CancelledError):
            # Leave RUNNING so the next invocation can explicitly recover it.
            raise
        except Exception as exc:
            with Storage(config.storage_path) as store: store.finish_campaign_window(name,window["window_utc"],run_id,f"{type(exc).__name__}: {exc}")
            progress(f"Campaign window failed: {type(exc).__name__}: {exc}")
        processed += 1
    with Storage(config.storage_path) as store:
        return {"campaign":name,"processed":processed,"run_ids":completed_runs,"summary":store.campaign_summary(name),"next_window_utc":store.next_campaign_window(name)}
