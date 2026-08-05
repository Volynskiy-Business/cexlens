from __future__ import annotations

import asyncio
import hashlib
import json
import os
import platform
import random
import socket
import subprocess
import uuid
from pathlib import Path
from typing import Callable

import httpx

from . import __version__
from .adapters import get_adapter
from .config import AppConfig
from .probes import probe_dns, probe_rest, probe_tcp, probe_tls, probe_websocket
from .reporting import generate_reports
from .scoring import rank
from .storage import Storage


def _git_sha() -> str | None:
    try: return subprocess.check_output(["git","rev-parse","HEAD"],text=True,stderr=subprocess.DEVNULL).strip()
    except Exception: return None


def _host_id() -> str: return hashlib.sha256(socket.gethostname().encode()).hexdigest()[:16]


async def benchmark(config: AppConfig, exchange_ids: list[str], iterations: int | None=None, ws_duration: int | None=None, progress: Callable[[str],None]=print) -> tuple[str,dict[str,str],list[dict]]:
    run_id=uuid.uuid4().hex[:12]; iterations=iterations or config.probes.iterations; ws_duration=ws_duration if ws_duration is not None else config.probes.websocket_observation_seconds
    with Storage(config.storage_path) as store:
        store.start_run(run_id,config.model_dump(),_host_id(),__version__,_git_sha())
        semaphore=asyncio.Semaphore(config.probes.bounded_concurrency)
        async with httpx.AsyncClient(timeout=config.probes.timeout_seconds,follow_redirects=True,headers={"User-Agent":"cexlatency/0.1 public-benchmark"}) as client:
            async def run_exchange(exchange_id: str) -> None:
                adapter=get_adapter(exchange_id); progress(f"[{exchange_id}] probing public endpoints")
                async with semaphore:
                    for fn in (probe_dns,probe_tcp,probe_tls): store.add_sample(await fn(run_id,adapter,adapter.rest_url,config.probes.timeout_seconds))
                    await asyncio.sleep(random.uniform(0,config.probes.jitter_ms/1000))
                    for i in range(iterations):
                        store.add_sample(await probe_rest(run_id,adapter,client,config.probes.timeout_seconds,False))
                        store.add_sample(await probe_rest(run_id,adapter,None,config.probes.timeout_seconds,True))
                        if i+1<iterations: await asyncio.sleep(random.uniform(0,config.probes.jitter_ms/1000))
                    if ws_duration>0: store.add_websocket(await probe_websocket(run_id,adapter,config.symbols["major"][0],ws_duration,config.probes.timeout_seconds))
            try:
                await asyncio.gather(*(run_exchange(e) for e in exchange_ids))
                store.finish_run(run_id)
            except (KeyboardInterrupt,asyncio.CancelledError):
                store.finish_run(run_id,"INTERRUPTED"); raise
        samples=store.samples(run_id); ws=store.websockets(run_id); rankings=rank(samples,ws,exchange_ids,config.scoring.weights)
        for row in rankings: store.save_score(run_id,row)
        paths=generate_reports(run_id,rankings,samples,config.report_directory)
        for kind,path in paths.items(): store.add_report(run_id,kind,path)
    return run_id,paths,rankings

