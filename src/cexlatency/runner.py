from __future__ import annotations

import asyncio
import hashlib
import json
import os
import platform
import random
import socket
import subprocess
import time
import uuid
import ssl
from pathlib import Path
from typing import Callable

import httpx

from . import __version__
from .adapters import get_adapter
from .config import AppConfig
from .probes import probe_dns, probe_rest, probe_tcp, probe_tls, probe_websocket
from .market_quality import collect_market_quality
from .diagnostics import detect_clock_status, detect_network_identity, summarize_route, trace_route
from .json_logging import JsonEventLogger
from .reporting import generate_reports
from .scoring import rank
from .storage import Storage


def _git_sha() -> str | None:
    try: return subprocess.check_output(["git","rev-parse","HEAD"],text=True,stderr=subprocess.DEVNULL).strip()
    except Exception: return None


def _host_id() -> str: return hashlib.sha256(socket.gethostname().encode()).hexdigest()[:16]


def _continue_rest_probing(iteration: int, minimum_iterations: int, deadline: float | None, now: float) -> bool:
    return iteration < minimum_iterations or (deadline is not None and now < deadline)


async def benchmark(config: AppConfig, exchange_ids: list[str], iterations: int | None=None, ws_duration: int | None=None, progress: Callable[[str],None]=print, duration_seconds: int | None=None) -> tuple[str,dict[str,str],list[dict]]:
    run_id=uuid.uuid4().hex[:12]; iterations=iterations or config.probes.iterations; ws_duration=ws_duration if ws_duration is not None else config.probes.websocket_observation_seconds
    logger=JsonEventLogger(Path(config.storage_path).with_suffix(".jsonl"))
    with Storage(config.storage_path) as store:
        host_id=_host_id(); clock=await detect_clock_status(); network=await detect_network_identity(host_id)
        store.start_run(run_id,config.model_dump(),host_id,__version__,_git_sha())
        store.upsert_host(host_id,host_id,platform.platform(),platform.python_version(),str(__import__("datetime").datetime.now().astimezone().tzinfo),clock,network)
        logger.emit("benchmark_started",run_id=run_id,exchanges=exchange_ids,version=__version__,clock_quality=clock.quality,duration_seconds=duration_seconds)
        if clock.quality != "VERIFIED":
            detail=f"clock quality={clock.quality}; source={clock.source}; measured_offset_ms={clock.offset_ms}"
            store.add_error(run_id,"__host__","local-clock","clock","CLOCK_QUALITY_UNKNOWN",detail)
            logger.probe_error(run_id,"__host__","local-clock","clock","CLOCK_QUALITY_UNKNOWN",detail)
        semaphore=asyncio.Semaphore(config.probes.bounded_concurrency)
        async with httpx.AsyncClient(timeout=config.probes.timeout_seconds,follow_redirects=True,headers={"User-Agent":"cexlatency/0.1 public-benchmark"}) as client:
            async def bounded(awaitable):
                async with semaphore:
                    return await awaitable

            async def run_exchange(exchange_id: str) -> None:
                adapter=get_adapter(exchange_id); progress(f"[{exchange_id}] probing public endpoints")
                exchange_semaphore=asyncio.Semaphore(config.probes.per_exchange_concurrency)
                async def exchange_bounded(awaitable):
                    async with exchange_semaphore:
                        return await bounded(awaitable)
                store.register_adapter(exchange_id,adapter.display_name,__version__,await adapter.discover_public_endpoints(),await adapter.list_supported_markets(),{"websocket":adapter.websocket_supported,"timestamp_fields":adapter.timestamp_fields,"rest_timestamp_fields":adapter.rest_timestamp_fields,"sequence_contiguous":adapter.sequence_contiguous,"rate_limit_policy":adapter.rate_limit_note,"notes":adapter.notes})
                tls_context=ssl.create_default_context(); tls_context.set_alpn_protocols(["h2","http/1.1"])
                diagnostic_urls=list(dict.fromkeys(url for url in (adapter.rest_url,adapter.ws_url) if url))
                diagnostic_samples=[]
                for diagnostic_url in diagnostic_urls:
                    diagnostic_samples.extend([
                        await exchange_bounded(probe_dns(run_id,adapter,diagnostic_url,config.probes.timeout_seconds,"first_observed")),
                        await exchange_bounded(probe_dns(run_id,adapter,diagnostic_url,config.probes.timeout_seconds,"warm")),
                        await exchange_bounded(probe_tcp(run_id,adapter,diagnostic_url,config.probes.timeout_seconds)),
                        await exchange_bounded(probe_tls(run_id,adapter,diagnostic_url,config.probes.timeout_seconds,tls_context,"full")),
                        await exchange_bounded(probe_tls(run_id,adapter,diagnostic_url,config.probes.timeout_seconds,tls_context,"resumption_attempt")),
                    ])
                for sample in diagnostic_samples:
                    store.add_sample(sample)
                    if not sample.success: logger.probe_error(run_id,exchange_id,sample.endpoint,sample.probe_type,sample.error_class,sample.error_detail)
                await asyncio.sleep(random.uniform(0,config.probes.jitter_ms/1000))
                for _ in range(config.probes.warmup_iterations):
                    warmup=await exchange_bounded(probe_rest(run_id,adapter,client,config.probes.timeout_seconds,False)); warmup.probe_type="rest_warmup"; store.add_sample(warmup)
                    if not warmup.success: logger.probe_error(run_id,exchange_id,warmup.endpoint,warmup.probe_type,warmup.error_class,warmup.error_detail)
                deadline=time.monotonic()+duration_seconds if duration_seconds else None; i=0
                while _continue_rest_probing(i,iterations,deadline,time.monotonic()):
                    for sample in (await exchange_bounded(probe_rest(run_id,adapter,client,config.probes.timeout_seconds,False)),await exchange_bounded(probe_rest(run_id,adapter,None,config.probes.timeout_seconds,True))):
                        store.add_sample(sample)
                        if not sample.success: logger.probe_error(run_id,exchange_id,sample.endpoint,sample.probe_type,sample.error_class,sample.error_detail)
                    i+=1
                    if _continue_rest_probing(i,iterations,deadline,time.monotonic()):
                        delay=random.uniform(0,config.probes.jitter_ms/1000)
                        if deadline is not None:
                            delay=min(max(delay,1.0),max(0.0,deadline-time.monotonic()))
                        if delay>0: await asyncio.sleep(delay)
                if ws_duration>0:
                    for symbol in config.benchmark_symbols():
                        ws_sample=await exchange_bounded(probe_websocket(run_id,adapter,symbol,ws_duration,config.probes.timeout_seconds,clock.quality)); store.add_websocket(ws_sample)
                        if not ws_sample.success: logger.probe_error(run_id,exchange_id,ws_sample.endpoint,"websocket",ws_sample.error_class,ws_sample.error_detail)
                if config.probes.market_quality:
                    for index, symbol in enumerate(config.benchmark_symbols()):
                        market=await collect_market_quality(run_id,adapter,symbol,client,index==0,exchange_bounded); store.add_orderbook(market)
                        if not market.success: logger.probe_error(run_id,exchange_id,"","orderbook",market.error_class,market.error_detail)
                if config.probes.route_diagnostics:
                    route_output=await exchange_bounded(trace_route(adapter.rest_url,config.probes.route_max_hops))
                    store.add_route(run_id,exchange_id,adapter.rest_url,route_output,summarize_route(route_output))
            try:
                await asyncio.gather(*(run_exchange(e) for e in exchange_ids))
                store.finish_run(run_id)
                logger.emit("benchmark_completed",run_id=run_id,status="COMPLETED")
            except (KeyboardInterrupt,asyncio.CancelledError):
                store.finish_run(run_id,"INTERRUPTED"); logger.emit("benchmark_completed",run_id=run_id,status="INTERRUPTED"); raise
            except Exception as exc:
                store.finish_run(run_id,"FAILED"); logger.emit("benchmark_completed",run_id=run_id,status="FAILED",exception_type=type(exc).__name__,detail=str(exc)); raise
        samples=store.samples(run_id); ws=store.websockets(run_id); markets=store.orderbooks(run_id); rankings=rank(samples,ws,exchange_ids,config.scoring.weights,markets,required_symbol_count=len(config.benchmark_symbols()))
        for row in rankings: store.save_score(run_id,row)
        paths=generate_reports(run_id,rankings,samples,config.report_directory,ws,markets,store.routes(run_id),config.campaign.timezone)
        for kind,path in paths.items(): store.add_report(run_id,kind,path)
    return run_id,paths,rankings
