from __future__ import annotations

import asyncio
import json
import socket
import ssl
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
import websockets

from .adapters import AdapterSpec
from .metrics import percentile
from .models import ProbeSample, WebSocketSummary, utc_now


def _host_port(url: str) -> tuple[str, int]:
    parsed = urlparse(url)
    return parsed.hostname or "", parsed.port or 443


async def probe_dns(run_id: str, adapter: AdapterSpec, url: str, timeout: float) -> ProbeSample:
    host, port = _host_port(url)
    started = time.perf_counter()
    try:
        infos = await asyncio.wait_for(asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM), timeout)
        elapsed = (time.perf_counter() - started) * 1000
        family, _, _, _, addr = infos[0]
        return ProbeSample(run_id, adapter.exchange_id, "dns", url, True, utc_now(), duration_ms=elapsed, dns_ms=elapsed, resolved_ip=addr[0], address_family="IPv6" if family == socket.AF_INET6 else "IPv4", metadata={"addresses": sorted({i[4][0] for i in infos})})
    except Exception as exc:
        return ProbeSample(run_id, adapter.exchange_id, "dns", url, False, utc_now(), duration_ms=(time.perf_counter()-started)*1000, error_class="DNS_FAILURE", error_detail=str(exc))


async def probe_tcp(run_id: str, adapter: AdapterSpec, url: str, timeout: float) -> ProbeSample:
    host, port = _host_port(url)
    started = time.perf_counter()
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
        elapsed = (time.perf_counter() - started) * 1000
        peer = writer.get_extra_info("peername")
        writer.close(); await writer.wait_closed()
        return ProbeSample(run_id, adapter.exchange_id, "tcp", url, True, utc_now(), duration_ms=elapsed, tcp_ms=elapsed, resolved_ip=peer[0] if peer else None)
    except Exception as exc:
        return ProbeSample(run_id, adapter.exchange_id, "tcp", url, False, utc_now(), duration_ms=(time.perf_counter()-started)*1000, error_class="TCP_TIMEOUT" if isinstance(exc, TimeoutError) else "TCP_FAILURE", error_detail=str(exc))


async def probe_tls(run_id: str, adapter: AdapterSpec, url: str, timeout: float) -> ProbeSample:
    host, port = _host_port(url)
    context = ssl.create_default_context()
    started = time.perf_counter()
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port, ssl=context, server_hostname=host), timeout)
        elapsed = (time.perf_counter() - started) * 1000
        ssl_obj = writer.get_extra_info("ssl_object")
        writer.close(); await writer.wait_closed()
        return ProbeSample(run_id, adapter.exchange_id, "tls", url, True, utc_now(), duration_ms=elapsed, tls_ms=elapsed, metadata={"tls_version": ssl_obj.version(), "alpn": ssl_obj.selected_alpn_protocol(), "cipher": ssl_obj.cipher()[0]})
    except Exception as exc:
        return ProbeSample(run_id, adapter.exchange_id, "tls", url, False, utc_now(), duration_ms=(time.perf_counter()-started)*1000, error_class="TLS_FAILURE", error_detail=str(exc))


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
        return ProbeSample(run_id, adapter.exchange_id, "rest_fresh" if fresh else "rest_reuse", adapter.rest_url, ok, utc_now(), duration_ms=elapsed, ttfb_ms=ttfb, status_code=response.status_code, payload_bytes=len(body), error_class=None if ok else ("HTTP_RATE_LIMIT" if response.status_code == 429 else "HTTP_SERVER_ERROR"), metadata={"rate_limit_headers": {k: v for k, v in response.headers.items() if "limit" in k.lower() or "remaining" in k.lower()}})
    except Exception as exc:
        return ProbeSample(run_id, adapter.exchange_id, "rest_fresh" if fresh else "rest_reuse", adapter.rest_url, False, utc_now(), duration_ms=(time.perf_counter()-started)*1000, ttfb_ms=ttfb, error_class="HTTP_TIMEOUT" if isinstance(exc, httpx.TimeoutException) else "HTTP_ERROR", error_detail=str(exc))
    finally:
        if own_client:
            await active.aclose()


def _find_timestamp(value: object, fields: tuple[str, ...]) -> float | None:
    if isinstance(value, dict):
        for field in fields:
            candidate = value.get(field)
            if isinstance(candidate, (int, float)):
                timestamp = float(candidate)
                if timestamp > 1e15: timestamp /= 1e6
                elif timestamp > 1e12: timestamp /= 1e3
                if timestamp > 1e9: return timestamp
        for nested in value.values():
            found = _find_timestamp(nested, fields)
            if found: return found
    elif isinstance(value, list):
        for nested in value[:5]:
            found = _find_timestamp(nested, fields)
            if found: return found
    return None


async def probe_websocket(run_id: str, adapter: AdapterSpec, symbol: str, duration: int, timeout: float) -> WebSocketSummary:
    if not adapter.ws_url:
        return WebSocketSummary(run_id, adapter.exchange_id, "", symbol, False, error_class="UNSUPPORTED_MARKET", error_detail=adapter.notes)
    started = time.perf_counter(); intervals: list[float] = []; lags: list[float] = []; last_message = None; malformed = 0; messages = 0
    try:
        async with asyncio.timeout(timeout + duration + 2):
            async with websockets.connect(adapter.ws_url, open_timeout=timeout, close_timeout=2, ping_interval=20, ping_timeout=10, additional_headers={"User-Agent": "cexlatency/0.1"}) as ws:
                handshake = (time.perf_counter() - started) * 1000
                subscription = adapter.subscription(symbol)
                sent = time.perf_counter()
                if subscription is not None:
                    await ws.send(json.dumps(subscription, separators=(",", ":")))
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
                    if first_ms is None: first_ms = (now_perf - started) * 1000
                    try:
                        data = json.loads(raw)
                        if ack_ms is None and isinstance(data, dict) and any(k in data for k in ("result", "event", "success", "id")):
                            ack_ms = (now_perf - sent) * 1000
                        else:
                            messages += 1
                            if last_message is not None: intervals.append((now_perf-last_message)*1000)
                            last_message = now_perf
                            ts = _find_timestamp(data, adapter.timestamp_fields)
                            if ts: lags.append((now_wall-ts)*1000)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        malformed += 1
        observed = max(time.perf_counter()-started, 0.001)
        return WebSocketSummary(run_id, adapter.exchange_id, adapter.ws_url, symbol, messages > 0, handshake, ack_ms, first_ms, messages, malformed, 0, messages/observed, percentile(intervals, .5) if intervals else None, percentile(intervals, .95) if intervals else None, percentile(lags, .5) if lags else None, "UNKNOWN", None if messages else "INSUFFICIENT_SAMPLE", None if messages else "no market-data message observed")
    except Exception as exc:
        return WebSocketSummary(run_id, adapter.exchange_id, adapter.ws_url, symbol, False, error_class="WS_HANDSHAKE_FAILURE" if messages == 0 else "WS_DISCONNECT", error_detail=str(exc), messages=messages, malformed_messages=malformed)
