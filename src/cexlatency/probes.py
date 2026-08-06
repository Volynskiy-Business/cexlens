from __future__ import annotations

import asyncio
import json
import gzip
import hashlib
import socket
import ssl
import statistics
import time
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

import httpx
import websockets

from .adapters import AdapterSpec
from .metrics import percentile
from .models import MarketDataEvent, ProbeSample, WebSocketSummary, utc_now


def _host_port(url: str) -> tuple[str, int]:
    parsed = urlparse(url)
    return parsed.hostname or "", parsed.port or 443


async def _close_writer(writer: asyncio.StreamWriter) -> None:
    """Close a completed probe without reclassifying peer shutdown quirks as probe failures."""
    writer.close()
    try:
        await writer.wait_closed()
    except (ConnectionError,OSError,ssl.SSLError):
        pass


@lru_cache(maxsize=1)
def _resolver_addresses() -> list[str]:
    """Best-effort resolver provenance without sending additional DNS traffic."""
    resolvers: list[str] = []
    path=Path("/etc/resolv.conf")
    if path.exists():
        try:
            resolvers=[line.split()[1] for line in path.read_text(encoding="utf-8",errors="ignore").splitlines() if line.strip().startswith("nameserver ")]
        except OSError:
            pass
    return list(dict.fromkeys(resolvers))


async def probe_dns(run_id: str, adapter: AdapterSpec, url: str, timeout: float, cache_state: str = "first_observed") -> ProbeSample:
    host, port = _host_port(url)
    started = time.perf_counter()
    try:
        infos = await asyncio.wait_for(asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM), timeout)
        elapsed = (time.perf_counter() - started) * 1000
        family, _, _, _, addr = infos[0]
        addresses=sorted({i[4][0] for i in infos})
        families=sorted({"IPv6" if i[0] == socket.AF_INET6 else "IPv4" for i in infos})
        return ProbeSample(run_id, adapter.exchange_id, f"dns_{cache_state}", url, True, utc_now(), duration_ms=elapsed, dns_ms=elapsed, resolved_ip=addr[0], address_family="IPv6" if family == socket.AF_INET6 else "IPv4", metadata={"addresses":addresses,"address_families":families,"resolver_addresses":_resolver_addresses(),"resolver_mode":"operating_system","cache_state":cache_state,"retry_count":0})
    except Exception as exc:
        return ProbeSample(run_id, adapter.exchange_id, f"dns_{cache_state}", url, False, utc_now(), duration_ms=(time.perf_counter()-started)*1000, error_class="DNS_FAILURE", error_detail=str(exc), metadata={"resolver_addresses":_resolver_addresses(),"resolver_mode":"operating_system","cache_state":cache_state,"retry_count":0})


async def probe_tcp(run_id: str, adapter: AdapterSpec, url: str, timeout: float) -> ProbeSample:
    host, port = _host_port(url)
    started = time.perf_counter()
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
        elapsed = (time.perf_counter() - started) * 1000
        peer = writer.get_extra_info("peername")
        await _close_writer(writer)
        peer_ip=peer[0] if peer else None
        return ProbeSample(run_id, adapter.exchange_id, "tcp", url, True, utc_now(), duration_ms=elapsed, tcp_ms=elapsed, resolved_ip=peer_ip,address_family="IPv6" if peer_ip and ":" in peer_ip else "IPv4",metadata={"retry_count":0})
    except Exception as exc:
        return ProbeSample(run_id, adapter.exchange_id, "tcp", url, False, utc_now(), duration_ms=(time.perf_counter()-started)*1000, error_class="TCP_TIMEOUT" if isinstance(exc, TimeoutError) else "TCP_FAILURE", error_detail=str(exc),metadata={"retry_count":0})


async def probe_tls(run_id: str, adapter: AdapterSpec, url: str, timeout: float, context: ssl.SSLContext | None = None, mode: str = "full") -> ProbeSample:
    host, port = _host_port(url)
    context = context or ssl.create_default_context()
    started = time.perf_counter()
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port, ssl=context, server_hostname=host), timeout)
        elapsed = (time.perf_counter() - started) * 1000
        ssl_obj = writer.get_extra_info("ssl_object")
        await _close_writer(writer)
        return ProbeSample(run_id, adapter.exchange_id, f"tls_{mode}", url, True, utc_now(), duration_ms=elapsed, tls_ms=elapsed, metadata={"tls_version": ssl_obj.version(), "alpn": ssl_obj.selected_alpn_protocol(), "cipher": ssl_obj.cipher()[0], "session_reused": bool(ssl_obj.session_reused), "certificate_validated":True,"mode": mode,"retry_count":0})
    except Exception as exc:
        return ProbeSample(run_id, adapter.exchange_id, f"tls_{mode}", url, False, utc_now(), duration_ms=(time.perf_counter()-started)*1000, error_class="TLS_FAILURE", error_detail=str(exc), metadata={"certificate_validated":False,"mode":mode,"retry_count":0})


async def probe_rest(run_id: str, adapter: AdapterSpec, client: httpx.AsyncClient | None, timeout: float, fresh: bool = False) -> ProbeSample:
    own_client = client is None or fresh
    active = httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers={"User-Agent": "cexlatency/0.1 public-benchmark"}) if own_client else client
    started = time.perf_counter()
    ttfb = None
    try:
        async with active.stream("GET", adapter.rest_url) as response:
            ttfb = (time.perf_counter() - started) * 1000
            body = await response.aread()
        elapsed = (time.perf_counter() - started) * 1000
        ok = 200 <= response.status_code < 400
        return ProbeSample(run_id, adapter.exchange_id, "rest_fresh" if fresh else "rest_reuse", adapter.rest_url, ok, utc_now(), duration_ms=elapsed, ttfb_ms=ttfb, status_code=response.status_code, payload_bytes=len(body), error_class=None if ok else ("HTTP_RATE_LIMIT" if response.status_code == 429 else "HTTP_SERVER_ERROR"), metadata={"rate_limit_headers": {k: v for k, v in response.headers.items() if "limit" in k.lower() or "remaining" in k.lower()},"retry_count":0})
    except Exception as exc:
        return ProbeSample(run_id, adapter.exchange_id, "rest_fresh" if fresh else "rest_reuse", adapter.rest_url, False, utc_now(), duration_ms=(time.perf_counter()-started)*1000, ttfb_ms=ttfb, error_class="HTTP_TIMEOUT" if isinstance(exc, httpx.TimeoutException) else "HTTP_ERROR", error_detail=str(exc),metadata={"retry_count":0})
    finally:
        if own_client:
            await active.aclose()


def _find_timestamp(value: object, fields: tuple[str, ...]) -> float | None:
    if isinstance(value, dict):
        for field in fields:
            candidate = value.get(field)
            if isinstance(candidate, (int, float)):
                timestamp = float(candidate)
                if timestamp > 1e17: timestamp /= 1e9
                elif timestamp > 1e14: timestamp /= 1e6
                elif timestamp > 1e11: timestamp /= 1e3
                if timestamp > 1e9: return timestamp
        for nested in value.values():
            found = _find_timestamp(nested, fields)
            if found: return found
    elif isinstance(value, list):
        for nested in value[:5]:
            found = _find_timestamp(nested, fields)
            if found: return found
    return None


def _find_sequence(value: object) -> int | None:
    if isinstance(value, dict):
        for field in ("u", "seq", "sequence", "version", "versionId"):
            candidate=value.get(field)
            if isinstance(candidate,(int,float,str)):
                try: return int(candidate)
                except (TypeError,ValueError): pass
        for nested in value.values():
            found=_find_sequence(nested)
            if found is not None: return found
    elif isinstance(value,list):
        for nested in value[:5]:
            found=_find_sequence(nested)
            if found is not None: return found
    return None


async def _resolve_websocket(adapter: AdapterSpec, timeout: float) -> tuple[str, str]:
    connection_url=adapter.ws_url
    reported_url=adapter.ws_url or adapter.ws_token_url or ""
    if adapter.ws_token_url:
        async with httpx.AsyncClient(timeout=timeout,headers={"User-Agent":"cexlatency/0.1 public-benchmark"}) as token_client:
            response=await token_client.post(adapter.ws_token_url); response.raise_for_status()
            token_data=response.json()["data"]; server=token_data["instanceServers"][0]["endpoint"]
            connection_url=f"{server}?token={token_data['token']}&connectId={uuid.uuid4().hex}"; reported_url=server
    if not connection_url: raise ValueError("no WebSocket connection URL resolved")
    return connection_url,reported_url


def _decode_message(raw: str | bytes) -> Any:
    if isinstance(raw,bytes) and raw.startswith(b"\x1f\x8b"): raw=gzip.decompress(raw)
    return json.loads(raw)


async def stream_market_data(adapter: AdapterSpec, symbol: str, duration_seconds: int, timeout: float = 10) -> AsyncIterator[MarketDataEvent]:
    connection_url,_=await _resolve_websocket(adapter,timeout)
    async with websockets.connect(connection_url,open_timeout=timeout,close_timeout=2,ping_interval=20,ping_timeout=10,additional_headers={"User-Agent":"cexlatency/0.1"}) as ws:
        subscription=adapter.subscription(symbol)
        if subscription is not None: await ws.send(json.dumps(subscription,separators=(",",":")))
        deadline=time.perf_counter()+duration_seconds
        while time.perf_counter()<deadline:
            try: raw=await asyncio.wait_for(ws.recv(),min(timeout,deadline-time.perf_counter()))
            except asyncio.TimeoutError: break
            data=_decode_message(raw)
            if isinstance(data,dict) and any(k in data for k in ("result","event","success","id")) and not any(k in data for k in ("data","book","orderbook_p","topic")): continue
            timestamp=_find_timestamp(data,adapter.timestamp_fields)
            yield MarketDataEvent(adapter.exchange_id,symbol,utc_now(),data,timestamp)


async def probe_websocket(run_id: str, adapter: AdapterSpec, symbol: str, duration: int, timeout: float, timestamp_quality: str = "UNKNOWN") -> WebSocketSummary:
    if not adapter.websocket_supported:
        return WebSocketSummary(run_id, adapter.exchange_id, "", symbol, False, error_class="UNSUPPORTED_MARKET", error_detail=adapter.notes)
    started = time.perf_counter(); intervals: list[float] = []; lags: list[float] = []; last_message = None; malformed = 0; messages = 0; heartbeat_rtt = None; sequence_gaps = 0; duplicates = 0; last_sequence = None; seen_hashes: set[bytes] = set()
    try:
        connection_url,reported_url=await _resolve_websocket(adapter,timeout)
        async with asyncio.timeout(timeout + duration + 2):
            async with websockets.connect(connection_url, open_timeout=timeout, close_timeout=2, ping_interval=20, ping_timeout=10, additional_headers={"User-Agent": "cexlatency/0.1"}) as ws:
                handshake = (time.perf_counter() - started) * 1000
                ping_started=time.perf_counter()
                pong=await ws.ping()
                await asyncio.wait_for(pong,min(timeout,5))
                heartbeat_rtt=(time.perf_counter()-ping_started)*1000
                subscription = adapter.subscription(symbol)
                sent = time.perf_counter()
                if subscription is not None:
                    await ws.send(json.dumps(subscription, separators=(",", ":")))
                observation_started=time.perf_counter()
                deadline = time.perf_counter() + duration
                ack_ms = None; first_ms = None
                while time.perf_counter() < deadline:
                    remaining = min(timeout, deadline - time.perf_counter())
                    if remaining <= 0: break
                    try:
                        raw = await asyncio.wait_for(ws.recv(), remaining)
                    except asyncio.TimeoutError:
                        # Reaching the quiet end of the requested observation
                        # window is a normal session completion, not a disconnect.
                        break
                    now_perf = time.perf_counter(); now_wall = datetime.now(timezone.utc).timestamp()
                    if isinstance(raw,bytes) and raw.startswith(b"\x1f\x8b"): raw=gzip.decompress(raw)
                    try:
                        data = _decode_message(raw)
                        if ack_ms is None and isinstance(data, dict) and any(k in data for k in ("result", "event", "success", "id")):
                            ack_ms = (now_perf - sent) * 1000
                        else:
                            if first_ms is None: first_ms = (now_perf - started) * 1000
                            messages += 1
                            digest=hashlib.blake2s(raw if isinstance(raw,bytes) else raw.encode(),digest_size=8).digest()
                            if digest in seen_hashes: duplicates+=1
                            elif len(seen_hashes)<10000: seen_hashes.add(digest)
                            if last_message is not None: intervals.append((now_perf-last_message)*1000)
                            last_message = now_perf
                            sequence=_find_sequence(data)
                            if adapter.sequence_contiguous and sequence is not None and last_sequence is not None:
                                if sequence==last_sequence: duplicates+=1
                                elif sequence>last_sequence+1: sequence_gaps+=sequence-last_sequence-1
                            if sequence is not None: last_sequence=sequence
                            ts = _find_timestamp(data, adapter.timestamp_fields)
                            if ts: lags.append((now_wall-ts)*1000)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        malformed += 1
        observed = max(time.perf_counter()-observation_started, 0.001)
        reconnect_ms=None; reconnect_failures=0
        try:
            reconnect_started=time.perf_counter()
            async with asyncio.timeout(timeout+5):
                async with websockets.connect(connection_url,open_timeout=timeout,close_timeout=2,ping_interval=20,ping_timeout=10,additional_headers={"User-Agent":"cexlatency/0.1"}) as reconnect_ws:
                    if subscription is not None: await reconnect_ws.send(json.dumps(subscription,separators=(",",":")))
                    while True:
                        reconnect_data=_decode_message(await reconnect_ws.recv())
                        if isinstance(reconnect_data,dict) and any(k in reconnect_data for k in ("result","event","success","id")) and not any(k in reconnect_data for k in ("data","book","orderbook_p","topic")): continue
                        reconnect_ms=(time.perf_counter()-reconnect_started)*1000
                        break
        except Exception:
            reconnect_failures=1
        median_interval=percentile(intervals,.5) if intervals else None
        stale_threshold=max(1000.0,3*median_interval) if median_interval is not None else 1000.0
        stale_periods=sum(value>stale_threshold for value in intervals)
        return WebSocketSummary(run_id,adapter.exchange_id,reported_url,symbol,messages>0,handshake_ms=handshake,ack_ms=ack_ms,first_message_ms=first_ms,messages=messages,malformed_messages=malformed,disconnects=reconnect_failures,message_rate_hz=messages/observed,mean_interval_ms=statistics.fmean(intervals) if intervals else None,median_interval_ms=median_interval,p95_interval_ms=percentile(intervals,.95) if intervals else None,median_observed_lag_ms=percentile(lags,.5) if lags else None,timestamp_quality=timestamp_quality,error_class=None if messages else "INSUFFICIENT_SAMPLE",error_detail=None if messages else "no market-data message observed",heartbeat_rtt_ms=heartbeat_rtt,sequence_gaps=sequence_gaps,duplicate_messages=duplicates,stale_periods=stale_periods,reconnect_ms=reconnect_ms,sequence_check_supported=adapter.sequence_contiguous)
    except Exception as exc:
        return WebSocketSummary(run_id, adapter.exchange_id, adapter.ws_url or adapter.ws_token_url or "", symbol, False, error_class="WS_HANDSHAKE_FAILURE" if messages == 0 else "WS_DISCONNECT", error_detail=str(exc), messages=messages, malformed_messages=malformed,disconnects=1 if messages else 0)
