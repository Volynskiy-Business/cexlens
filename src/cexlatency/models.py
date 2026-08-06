from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Endpoint:
    exchange_id: str
    kind: str
    url: str
    purpose: str = "public"


@dataclass(frozen=True)
class Market:
    exchange_id: str
    canonical_symbol: str
    native_symbol: str
    market_type: str = "linear_perpetual"


@dataclass
class ProbeSample:
    run_id: str
    exchange_id: str
    probe_type: str
    endpoint: str
    success: bool
    started_at: str
    duration_ms: float | None = None
    dns_ms: float | None = None
    tcp_ms: float | None = None
    tls_ms: float | None = None
    ttfb_ms: float | None = None
    status_code: int | None = None
    payload_bytes: int | None = None
    resolved_ip: str | None = None
    address_family: str | None = None
    error_class: str | None = None
    error_detail: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WebSocketSummary:
    run_id: str
    exchange_id: str
    endpoint: str
    symbol: str
    success: bool
    handshake_ms: float | None = None
    ack_ms: float | None = None
    first_message_ms: float | None = None
    messages: int = 0
    malformed_messages: int = 0
    disconnects: int = 0
    message_rate_hz: float = 0.0
    median_interval_ms: float | None = None
    p95_interval_ms: float | None = None
    median_observed_lag_ms: float | None = None
    timestamp_quality: str = "UNKNOWN"
    error_class: str | None = None
    error_detail: str | None = None
    heartbeat_rtt_ms: float | None = None
    sequence_gaps: int = 0
    duplicate_messages: int = 0
    stale_periods: int = 0
    reconnect_ms: float | None = None
    sequence_check_supported: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OrderBookQuality:
    run_id: str
    exchange_id: str
    symbol: str
    native_symbol: str
    success: bool
    observed_at: str
    best_bid: float | None = None
    best_ask: float | None = None
    spread_bps: float | None = None
    bid_top_size: float | None = None
    ask_top_size: float | None = None
    bid_depth_5bps: float | None = None
    ask_depth_5bps: float | None = None
    bid_depth_10bps: float | None = None
    ask_depth_10bps: float | None = None
    bid_depth_25bps: float | None = None
    ask_depth_25bps: float | None = None
    volume_24h: float | None = None
    quote_volume_24h: float | None = None
    open_interest: float | None = None
    funding_rate: float | None = None
    futures_market_count: int | None = None
    snapshot_latency_ms: float | None = None
    timestamp_quality: str = "EXCHANGE_PROVIDED"
    error_class: str | None = None
    error_detail: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ClockStatus:
    synchronized: bool | None
    quality: str
    source: str | None
    offset_ms: float | None
    checked_at: str
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MarketDataEvent:
    exchange_id: str
    symbol: str
    received_at: str
    payload: dict[str, Any] | list[Any]
    exchange_timestamp: float | None = None
