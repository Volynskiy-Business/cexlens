from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import Endpoint, Market


@dataclass(frozen=True)
class AdapterSpec:
    exchange_id: str
    display_name: str
    rest_url: str
    ws_url: str | None
    ws_subscribe: dict[str, Any] | None = None
    symbol_template: str = "{base}USDT"
    timestamp_fields: tuple[str, ...] = ("E", "ts", "time", "timestamp")
    notes: str = ""
    market_metadata_url: str | None = None

    async def discover_public_endpoints(self) -> list[Endpoint]:
        endpoints = [Endpoint(self.exchange_id, "rest", self.rest_url, "server_time_or_ticker")]
        if self.ws_url:
            endpoints.append(Endpoint(self.exchange_id, "websocket", self.ws_url, "public_market_data"))
        if self.market_metadata_url:
            endpoints.append(Endpoint(self.exchange_id, "rest", self.market_metadata_url, "market_metadata"))
        return endpoints

    async def list_supported_markets(self) -> list[Market]:
        return [Market(self.exchange_id, s, self.native_symbol(s)) for s in ("BTCUSDT", "ETHUSDT", "SOLUSDT")]

    def native_symbol(self, symbol: str) -> str:
        base = symbol.removesuffix("USDT")
        return self.symbol_template.format(base=base, symbol=symbol)

    def subscription(self, symbol: str) -> dict[str, Any] | None:
        if self.ws_subscribe is None:
            return None
        native = self.native_symbol(symbol)
        return _format_recursive(self.ws_subscribe, symbol=symbol, native=native, lower=native.lower())


def _format_recursive(value: Any, **values: str) -> Any:
    if isinstance(value, str):
        return value.format(**values)
    if isinstance(value, list):
        return [_format_recursive(v, **values) for v in value]
    if isinstance(value, dict):
        return {k: _format_recursive(v, **values) for k, v in value.items()}
    return value


SPECS = [
    AdapterSpec("binance", "Binance", "https://fapi.binance.com/fapi/v1/time", "wss://fstream.binance.com/ws", {"method": "SUBSCRIBE", "params": ["{lower}@bookTicker"], "id": 1}, market_metadata_url="https://fapi.binance.com/fapi/v1/exchangeInfo"),
    AdapterSpec("bybit", "Bybit", "https://api.bybit.com/v5/market/time", "wss://stream.bybit.com/v5/public/linear", {"op": "subscribe", "args": ["orderbook.1.{native}"]}, market_metadata_url="https://api.bybit.com/v5/market/instruments-info?category=linear"),
    AdapterSpec("okx", "OKX", "https://www.okx.com/api/v5/public/time", "wss://ws.okx.com:8443/ws/v5/public", {"op": "subscribe", "args": [{"channel": "books5", "instId": "{native}"}]}, symbol_template="{base}-USDT-SWAP", market_metadata_url="https://www.okx.com/api/v5/public/instruments?instType=SWAP"),
    AdapterSpec("bitget", "Bitget", "https://api.bitget.com/api/v2/public/time", "wss://ws.bitget.com/v2/ws/public", {"op": "subscribe", "args": [{"instType": "USDT-FUTURES", "channel": "books1", "instId": "{native}"}]}, market_metadata_url="https://api.bitget.com/api/v2/mix/market/contracts?productType=usdt-futures"),
    AdapterSpec("gate", "Gate.io", "https://api.gateio.ws/api/v4/futures/usdt/contracts/BTC_USDT", "wss://fx-ws.gateio.ws/v4/ws/usdt", {"time": 0, "channel": "futures.book_ticker", "event": "subscribe", "payload": ["{native}"]}, symbol_template="{base}_USDT", market_metadata_url="https://api.gateio.ws/api/v4/futures/usdt/contracts"),
    AdapterSpec("mexc", "MEXC", "https://contract.mexc.com/api/v1/contract/ping", "wss://contract.mexc.com/edge", {"method": "sub.depth", "param": {"symbol": "{native}"}}, symbol_template="{base}_USDT", market_metadata_url="https://contract.mexc.com/api/v1/contract/detail"),
    AdapterSpec("kucoin", "KuCoin Futures", "https://api-futures.kucoin.com/api/v1/timestamp", None, notes="WebSocket requires a short-lived public bullet token; REST supported in MVP.", symbol_template="{base}USDTM", market_metadata_url="https://api-futures.kucoin.com/api/v1/contracts/active"),
    AdapterSpec("kraken", "Kraken Futures", "https://futures.kraken.com/derivatives/api/v3/tickers", "wss://futures.kraken.com/ws/v1", {"event": "subscribe", "feed": "ticker", "product_ids": ["{native}"]}, symbol_template="PI_{base}USD", market_metadata_url="https://futures.kraken.com/derivatives/api/v3/instruments"),
    AdapterSpec("bingx", "BingX", "https://open-api.bingx.com/openApi/swap/v2/server/time", "wss://open-api-swap.bingx.com/swap-market", {"id": "cexlatency", "reqType": "sub", "dataType": "{native}@bookTicker"}, symbol_template="{base}-USDT", market_metadata_url="https://open-api.bingx.com/openApi/swap/v2/quote/contracts"),
    AdapterSpec("phemex", "Phemex", "https://api.phemex.com/public/time", "wss://ws.phemex.com", {"id": 1, "method": "orderbook.subscribe", "params": ["{native}"]}, symbol_template="{base}USDT", market_metadata_url="https://api.phemex.com/public/products"),
]

REGISTRY = {spec.exchange_id: spec for spec in SPECS}


def get_adapter(exchange_id: str) -> AdapterSpec:
    try:
        return REGISTRY[exchange_id]
    except KeyError as exc:
        raise ValueError(f"unsupported exchange: {exchange_id}") from exc

