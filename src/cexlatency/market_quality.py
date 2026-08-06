from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable,Callable
from datetime import datetime
from typing import Any

import httpx

from .adapters import AdapterSpec
from .models import OrderBookQuality, utc_now


def _number(value: Any) -> float | None:
    try:
        result = float(value)
        return result if result == result else None
    except (TypeError, ValueError):
        return None


def _at(payload: Any, *path: str | int) -> Any:
    value = payload
    for part in path:
        try:
            value = value[part]
        except (KeyError, IndexError, TypeError):
            return None
    return value


def _levels(values: Any) -> list[tuple[float, float]]:
    result: list[tuple[float, float]] = []
    if not isinstance(values, list):
        return result
    for row in values:
        if isinstance(row, (list, tuple)) and len(row) >= 2:
            price, size = _number(row[0]), _number(row[1])
        elif isinstance(row, dict):
            price = _number(row.get("price", row.get("p")))
            size = _number(row.get("qty", row.get("size", row.get("s", row.get("q", row.get("volume"))))))
        else:
            continue
        if price is not None and size is not None and price > 0 and size >= 0:
            result.append((price, size))
    return result


def extract_book(exchange_id: str, payload: Any) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    paths: dict[str, tuple[tuple[str | int, ...], tuple[str | int, ...]]] = {
        "binance": (("bids",), ("asks",)),
        "bybit": (("result", "b"), ("result", "a")),
        "okx": (("data", 0, "bids"), ("data", 0, "asks")),
        "bitget": (("data", "bids"), ("data", "asks")),
        "gate": (("bids",), ("asks",)),
        "mexc": (("data", "bids"), ("data", "asks")),
        "kucoin": (("data", "bids"), ("data", "asks")),
        "kraken": (("orderBook", "bids"), ("orderBook", "asks")),
        "bingx": (("data", "bids"), ("data", "asks")),
        "phemex": (("result", "orderbook_p", "bids"), ("result", "orderbook_p", "asks")),
    }
    bid_path, ask_path = paths[exchange_id]
    return _levels(_at(payload, *bid_path)), _levels(_at(payload, *ask_path))


def extract_ticker(exchange_id: str, payload: Any, native_symbol: str) -> dict[str, float | None]:
    row: Any = payload
    if exchange_id in {"bybit", "bitget"}:
        row = _at(payload, "result" if exchange_id == "bybit" else "data", "list" if exchange_id == "bybit" else 0)
        if exchange_id == "bybit": row = _at(payload, "result", "list", 0)
    elif exchange_id == "okx": row = _at(payload, "data", 0)
    elif exchange_id == "gate": row = _at(payload, 0)
    elif exchange_id in {"mexc", "kucoin", "bingx"}: row = _at(payload, "data")
    elif exchange_id == "kraken":
        rows = payload.get("tickers", []) if isinstance(payload, dict) else []
        row = next((item for item in rows if str(item.get("symbol", item.get("product_id", ""))).upper() == native_symbol.upper()), {})
    elif exchange_id == "phemex": row = _at(payload, "result")
    row = row if isinstance(row, dict) else {}
    fields = {
        "binance": ("volume", "quoteVolume", "openInterest", "lastFundingRate"),
        "bybit": ("volume24h", "turnover24h", "openInterest", "fundingRate"),
        "okx": ("vol24h", "volCcy24h", "oi", "fundingRate"),
        "bitget": ("baseVolume", "quoteVolume", "openInterest", "fundingRate"),
        "gate": ("volume_24h_base", "volume_24h_quote", "open_interest", "funding_rate"),
        "mexc": ("volume24", "amount24", "holdVol", "fundingRate"),
        "kucoin": ("volume", "turnover", "openInterest", "fundingFeeRate"),
        "kraken": ("volume", "volumeQuote", "openInterest", "funding_rate"),
        "bingx": ("volume", "quoteVolume", "openInterest", "fundingRate"),
        "phemex": ("volumeRq", "turnoverRv", "openInterestRv", "fundingRateRr"),
    }
    volume, quote, oi, funding = fields[exchange_id]
    return {"volume_24h": _number(row.get(volume)), "quote_volume_24h": _number(row.get(quote)), "open_interest": _number(row.get(oi)), "funding_rate": _number(row.get(funding))}


def extract_market_count(exchange_id: str, payload: Any) -> int | None:
    rows: Any
    if exchange_id == "binance":
        rows = _at(payload, "symbols")
        return sum(1 for r in rows or [] if r.get("contractType") == "PERPETUAL" and r.get("quoteAsset") == "USDT")
    if exchange_id == "bybit": rows = _at(payload, "result", "list")
    elif exchange_id == "okx": rows = _at(payload, "data")
    elif exchange_id == "bitget": rows = _at(payload, "data")
    elif exchange_id == "gate": rows = payload
    elif exchange_id in {"mexc", "kucoin", "bingx"}: rows = _at(payload, "data")
    elif exchange_id == "kraken": rows = payload.get("instruments") if isinstance(payload, dict) else None
    elif exchange_id == "phemex": rows = _at(payload, "data", "perpProductsV2") or _at(payload, "data", "products")
    else: rows = None
    return len(rows) if isinstance(rows, list) else None


def _epoch_seconds(value: Any) -> float | None:
    if isinstance(value,str) and not value.replace(".","",1).isdigit():
        try: return datetime.fromisoformat(value.replace("Z","+00:00")).timestamp()
        except ValueError: return None
    timestamp=_number(value)
    if timestamp is None: return None
    if timestamp > 1e17: timestamp /= 1e9
    elif timestamp > 1e14: timestamp /= 1e6
    elif timestamp > 1e11: timestamp /= 1e3
    return timestamp if timestamp > 1e9 else None


def extract_trade_frequency(exchange_id: str, payload: Any) -> dict[str,float | int | None]:
    if exchange_id == "binance": rows=payload
    elif exchange_id == "bybit": rows=_at(payload,"result","list")
    elif exchange_id in {"okx","bitget","mexc","kucoin","bingx"}: rows=_at(payload,"data")
    elif exchange_id == "gate": rows=payload
    elif exchange_id == "kraken": rows=_at(payload,"history")
    elif exchange_id == "phemex": rows=_at(payload,"result","trades_p")
    else: rows=None
    if not isinstance(rows,list): raise ValueError("recent-trade response has no usable list")
    fields={"binance":"time","bybit":"time","okx":"ts","bitget":"ts","gate":"create_time","mexc":"t","kucoin":"ts","kraken":"time","bingx":"time"}
    timestamps=[]
    for row in rows:
        value=row[0] if exchange_id=="phemex" and isinstance(row,list) and row else row.get(fields.get(exchange_id,"")) if isinstance(row,dict) else None
        timestamp=_epoch_seconds(value)
        if timestamp is not None: timestamps.append(timestamp)
    span=max(timestamps)-min(timestamps) if len(timestamps)>=2 else None
    frequency=(len(timestamps)-1)/span if span and span>0 else None
    return {"trade_count_sample":len(timestamps),"trade_sample_span_seconds":span,"trade_frequency_hz":frequency}


def calculate_depth(bids: list[tuple[float, float]], asks: list[tuple[float, float]]) -> dict[str, float]:
    if not bids or not asks:
        raise ValueError("order book has no usable bid/ask levels")
    best_bid = max(bids, key=lambda item: item[0])
    best_ask = min(asks, key=lambda item: item[0])
    mid = (best_bid[0] + best_ask[0]) / 2
    if mid <= 0 or best_ask[0] < best_bid[0]:
        raise ValueError("order book is crossed or invalid")
    result = {
        "best_bid": best_bid[0], "best_ask": best_ask[0],
        "bid_top_size": best_bid[1], "ask_top_size": best_ask[1],
        "spread_bps": (best_ask[0] - best_bid[0]) / mid * 10_000,
    }
    for bps in (5, 10, 25):
        bid_floor = mid * (1 - bps / 10_000)
        ask_ceiling = mid * (1 + bps / 10_000)
        result[f"bid_depth_{bps}bps"] = sum(price * size for price, size in bids if price >= bid_floor)
        result[f"ask_depth_{bps}bps"] = sum(price * size for price, size in asks if price <= ask_ceiling)
    return result


async def _json(client: httpx.AsyncClient, url: str | None) -> Any:
    if not url:
        return None
    response = await client.get(url)
    response.raise_for_status()
    return response.json()


async def collect_market_quality(run_id: str, adapter: AdapterSpec, symbol: str, client: httpx.AsyncClient, include_market_count: bool = False, request_limiter: Callable[[Awaitable[Any]],Awaitable[Any]] | None = None) -> OrderBookQuality:
    native = adapter.native_symbol(symbol)
    started = time.perf_counter()
    try:
        urls = [adapter.formatted_url(adapter.orderbook_url, symbol), adapter.formatted_url(adapter.ticker_url, symbol), adapter.formatted_url(adapter.open_interest_url, symbol), adapter.formatted_url(adapter.funding_url, symbol),adapter.formatted_url(adapter.trades_url,symbol)]
        async def fetch(url: str | None) -> Any:
            request=_json(client,url)
            return await request_limiter(request) if request_limiter else await request
        book_payload, ticker_payload, oi_payload, funding_payload, trades_payload = await asyncio.gather(*(fetch(u) for u in urls))
        latency_ms = (time.perf_counter() - started) * 1000
        bids, asks = extract_book(adapter.exchange_id, book_payload)
        depth = calculate_depth(bids, asks)
        ticker = extract_ticker(adapter.exchange_id, ticker_payload, native)
        trades=extract_trade_frequency(adapter.exchange_id,trades_payload)
        if isinstance(oi_payload, dict):
            oi_row = _at(oi_payload, "data", 0) if adapter.exchange_id == "okx" else oi_payload
            if isinstance(oi_row, dict): ticker["open_interest"] = _number(oi_row.get("openInterest", oi_row.get("oi"))) or ticker["open_interest"]
        if isinstance(funding_payload, dict):
            funding_row = _at(funding_payload, "data", 0) if adapter.exchange_id == "okx" else funding_payload
            if isinstance(funding_row, dict): ticker["funding_rate"] = _number(funding_row.get("lastFundingRate", funding_row.get("fundingRate"))) or ticker["funding_rate"]
        market_count = None
        if include_market_count and adapter.market_metadata_url:
            market_count = extract_market_count(adapter.exchange_id, await fetch(adapter.market_metadata_url))
        return OrderBookQuality(run_id, adapter.exchange_id, symbol, native, True, utc_now(), snapshot_latency_ms=latency_ms, futures_market_count=market_count, metadata={"depth_unit": "approximate_quote_notional", "source": "exchange_public_api","trade_frequency_method":"recent_public_trades_sample"}, **depth, **ticker,**trades)
    except Exception as exc:
        return OrderBookQuality(run_id, adapter.exchange_id, symbol, native, False, utc_now(), snapshot_latency_ms=(time.perf_counter()-started)*1000, error_class="MARKET_DATA_ERROR", error_detail=f"{type(exc).__name__}: {exc}")
