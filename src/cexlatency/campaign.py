from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo

from .config import AppConfig
from .models import utc_now
from .runner import benchmark
from .storage import Storage


def build_schedule(config: AppConfig, start_local_date: datetime | None = None) -> list[tuple[str, str]]:
    zone = ZoneInfo(config.campaign.timezone)
    start = start_local_date.astimezone(zone) if start_local_date else datetime.now(zone)
    rows: list[tuple[str, str]] = []
    for day_offset in range(config.campaign.duration_days):
        date = start.date() + timedelta(days=day_offset)
        for hhmm in config.campaign.windows_local:
            hour, minute = map(int, hhmm.split(":"))
            local = datetime(date.year,date.month,date.day,hour,minute,tzinfo=zone)
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
) -> dict[str, Any]:
    name = config.campaign.name
    completed_runs: list[str] = []
    with Storage(config.storage_path) as store:
        if store.campaign_window_count(name)==0:
            store.ensure_campaign_windows(name, build_schedule(config))
        recovered = store.resume_campaign(name)
    if recovered: progress(f"Recovered {recovered} interrupted campaign window(s)")
    processed = 0
    while processed < max_windows:
        with Storage(config.storage_path) as store:
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
        with Storage(config.storage_path) as store:
            if not store.claim_campaign_window(name,window["window_utc"]): continue
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
