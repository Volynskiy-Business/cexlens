from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Protocol

from .models import Endpoint, Market, MarketDataEvent, ProbeSample, WebSocketSummary


class ExchangeAdapter(Protocol):
    exchange_id: str
    display_name: str

    async def discover_public_endpoints(self) -> list[Endpoint]: ...
    async def list_supported_markets(self) -> list[Market]: ...
    async def probe_rest(self, endpoint: Endpoint | None = None, run_id: str = "adhoc", timeout: float = 10) -> ProbeSample: ...
    async def probe_websocket(self, endpoint: Endpoint | None = None, run_id: str = "adhoc", symbol: str = "BTCUSDT", duration_seconds: int = 5, timeout: float = 10) -> WebSocketSummary: ...
    def subscribe_order_book(self, symbol: str, duration_seconds: int) -> AsyncIterator[MarketDataEvent]: ...


@dataclass(frozen=True)
class AdapterSpec:
    exchange_id: str
    display_name: str
    rest_url: str
    ws_url: str | None
    ws_subscribe: dict[str, Any] | None = None
    symbol_template: str = "{base}USDT"
    timestamp_fields: tuple[str, ...] = ("E", "ts", "time", "timestamp")
    rest_timestamp_fields: tuple[str, ...] = ("serverTime", "timeSecond", "timeNano", "time", "ts", "timestamp")
    notes: str = ""
    market_metadata_url: str | None = None
    orderbook_url: str | None = None
    ticker_url: str | None = None
    open_interest_url: str | None = None
    funding_url: str | None = None
    trades_url: str | None = None
    ws_token_url: str | None = None
    symbol_aliases: dict[str, str] = field(default_factory=dict)
    sequence_contiguous: bool = False
    rate_limit_note: str = "CEXLENS uses bounded concurrency, one measured stream, and randomized inter-request jitter."

    async def discover_public_endpoints(self) -> list[Endpoint]:
        endpoints = [Endpoint(self.exchange_id, "rest", self.rest_url, "server_time_or_ticker")]
        if self.ws_url or self.ws_token_url:
            endpoints.append(Endpoint(self.exchange_id, "websocket", self.ws_url or self.ws_token_url or "", "public_market_data"))
        if self.market_metadata_url:
            endpoints.append(Endpoint(self.exchange_id, "rest", self.market_metadata_url, "market_metadata"))
        if self.trades_url:
            endpoints.append(Endpoint(self.exchange_id, "rest", self.trades_url, "recent_public_trades"))
        return endpoints

    async def list_supported_markets(self) -> list[Market]:
        return [Market(self.exchange_id, s, self.native_symbol(s)) for s in ("BTCUSDT", "ETHUSDT", "SOLUSDT")]

    def native_symbol(self, symbol: str) -> str:
        if symbol in self.symbol_aliases:
            return self.symbol_aliases[symbol]
        base = symbol.removesuffix("USDT")
        return self.symbol_template.format(base=base, symbol=symbol)

    def subscription(self, symbol: str) -> dict[str, Any] | None:
        if self.ws_subscribe is None:
            return None
        native = self.native_symbol(symbol)
        return _format_recursive(self.ws_subscribe, symbol=symbol, native=native, lower=native.lower())

    def formatted_url(self, template: str | None, symbol: str) -> str | None:
        if not template:
            return None
        native = self.native_symbol(symbol)
        return template.format(symbol=symbol, native=native, lower=native.lower(), base=symbol.removesuffix("USDT"))

    @property
    def websocket_supported(self) -> bool:
        return bool(self.ws_url or self.ws_token_url)

    async def probe_rest(self, endpoint: Endpoint | None = None, run_id: str = "adhoc", timeout: float = 10) -> ProbeSample:
        import httpx
        from .probes import probe_rest
        async with httpx.AsyncClient(timeout=timeout,follow_redirects=True) as client:
            return await probe_rest(run_id,self,client,timeout)

    async def probe_websocket(self, endpoint: Endpoint | None = None, run_id: str = "adhoc", symbol: str = "BTCUSDT", duration_seconds: int = 5, timeout: float = 10) -> WebSocketSummary:
        from .probes import probe_websocket
        return await probe_websocket(run_id,self,symbol,duration_seconds,timeout)

    async def subscribe_order_book(self, symbol: str, duration_seconds: int) -> AsyncIterator[MarketDataEvent]:
        from .probes import stream_market_data
        async for event in stream_market_data(self,symbol,duration_seconds):
            yield event


def _format_recursive(value: Any, **values: str) -> Any:
    if isinstance(value, str):
        return value.format(**values)
    if isinstance(value, list):
        return [_format_recursive(v, **values) for v in value]
    if isinstance(value, dict):
        return {k: _format_recursive(v, **values) for k, v in value.items()}
    return value


SPECS = [
    AdapterSpec("binance", "Binance", "https://fapi.binance.com/fapi/v1/time", "wss://fstream.binance.com/ws", {"method": "SUBSCRIBE", "params": ["{lower}@bookTicker"], "id": 1}, market_metadata_url="https://fapi.binance.com/fapi/v1/exchangeInfo", orderbook_url="https://fapi.binance.com/fapi/v1/depth?symbol={native}&limit=100", ticker_url="https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={native}", open_interest_url="https://fapi.binance.com/fapi/v1/openInterest?symbol={native}", funding_url="https://fapi.binance.com/fapi/v1/premiumIndex?symbol={native}",trades_url="https://fapi.binance.com/fapi/v1/trades?symbol={native}&limit=100"),
    AdapterSpec("bybit", "Bybit", "https://api.bybit.com/v5/market/time", "wss://stream.bybit.com/v5/public/linear", {"op": "subscribe", "args": ["orderbook.1.{native}"]}, market_metadata_url="https://api.bybit.com/v5/market/instruments-info?category=linear&limit=1000", orderbook_url="https://api.bybit.com/v5/market/orderbook?category=linear&symbol={native}&limit=200", ticker_url="https://api.bybit.com/v5/market/tickers?category=linear&symbol={native}",trades_url="https://api.bybit.com/v5/market/recent-trade?category=linear&symbol={native}&limit=100"),
    AdapterSpec("okx", "OKX", "https://www.okx.com/api/v5/public/time", "wss://ws.okx.com:8443/ws/v5/public", {"op": "subscribe", "args": [{"channel": "books5", "instId": "{native}"}]}, symbol_template="{base}-USDT-SWAP", market_metadata_url="https://www.okx.com/api/v5/public/instruments?instType=SWAP", orderbook_url="https://www.okx.com/api/v5/market/books?instId={native}&sz=400", ticker_url="https://www.okx.com/api/v5/market/ticker?instId={native}", open_interest_url="https://www.okx.com/api/v5/public/open-interest?instType=SWAP&instId={native}", funding_url="https://www.okx.com/api/v5/public/funding-rate?instId={native}",trades_url="https://www.okx.com/api/v5/market/trades?instId={native}&limit=100"),
    AdapterSpec("bitget", "Bitget", "https://api.bitget.com/api/v2/public/time", "wss://ws.bitget.com/v2/ws/public", {"op": "subscribe", "args": [{"instType": "USDT-FUTURES", "channel": "books1", "instId": "{native}"}]}, market_metadata_url="https://api.bitget.com/api/v2/mix/market/contracts?productType=usdt-futures", orderbook_url="https://api.bitget.com/api/v2/mix/market/merge-depth?symbol={native}&productType=USDT-FUTURES&precision=scale0&limit=100", ticker_url="https://api.bitget.com/api/v2/mix/market/ticker?symbol={native}&productType=USDT-FUTURES",trades_url="https://api.bitget.com/api/v2/mix/market/fills?symbol={native}&productType=USDT-FUTURES&limit=100"),
    AdapterSpec("gate", "Gate.io", "https://api.gateio.ws/api/v4/futures/usdt/contracts/BTC_USDT", "wss://fx-ws.gateio.ws/v4/ws/usdt", {"time": 0, "channel": "futures.book_ticker", "event": "subscribe", "payload": ["{native}"]}, symbol_template="{base}_USDT", market_metadata_url="https://api.gateio.ws/api/v4/futures/usdt/contracts", orderbook_url="https://api.gateio.ws/api/v4/futures/usdt/order_book?contract={native}&limit=100", ticker_url="https://api.gateio.ws/api/v4/futures/usdt/tickers?contract={native}",trades_url="https://api.gateio.ws/api/v4/futures/usdt/trades?contract={native}&limit=100"),
    AdapterSpec("mexc", "MEXC", "https://contract.mexc.com/api/v1/contract/ping", "wss://contract.mexc.com/edge", {"method": "sub.depth", "param": {"symbol": "{native}"}}, symbol_template="{base}_USDT", market_metadata_url="https://contract.mexc.com/api/v1/contract/detail", orderbook_url="https://contract.mexc.com/api/v1/contract/depth/{native}", ticker_url="https://contract.mexc.com/api/v1/contract/ticker?symbol={native}",trades_url="https://contract.mexc.com/api/v1/contract/deals/{native}"),
    AdapterSpec("kucoin", "KuCoin Futures", "https://api-futures.kucoin.com/api/v1/timestamp", None, {"id": "cexlatency", "type": "subscribe", "topic": "/contractMarket/level2Depth5:{native}", "privateChannel": False, "response": True}, notes="WebSocket uses a short-lived public bullet token discovered at runtime.", symbol_template="{base}USDTM", market_metadata_url="https://api-futures.kucoin.com/api/v1/contracts/active", orderbook_url="https://api-futures.kucoin.com/api/v1/level2/snapshot?symbol={native}", ticker_url="https://api-futures.kucoin.com/api/v1/ticker?symbol={native}", ws_token_url="https://api-futures.kucoin.com/api/v1/bullet-public", symbol_aliases={"BTCUSDT": "XBTUSDTM"},trades_url="https://api-futures.kucoin.com/api/v1/trade/history?symbol={native}"),
    AdapterSpec("kraken", "Kraken Futures", "https://futures.kraken.com/derivatives/api/v3/tickers", "wss://futures.kraken.com/ws/v1", {"event": "subscribe", "feed": "ticker", "product_ids": ["{native}"]}, symbol_template="PI_{base}USD", market_metadata_url="https://futures.kraken.com/derivatives/api/v3/instruments", orderbook_url="https://futures.kraken.com/derivatives/api/v3/orderbook?symbol={native}", ticker_url="https://futures.kraken.com/derivatives/api/v3/tickers", symbol_aliases={"BTCUSDT": "PI_XBTUSD", "SOLUSDT": "PF_SOLUSD"},trades_url="https://futures.kraken.com/derivatives/api/v3/history?symbol={native}"),
    AdapterSpec("bingx", "BingX", "https://open-api.bingx.com/openApi/swap/v2/server/time", "wss://open-api-swap.bingx.com/swap-market", {"id": "cexlatency", "reqType": "sub", "dataType": "{native}@bookTicker"}, symbol_template="{base}-USDT", market_metadata_url="https://open-api.bingx.com/openApi/swap/v2/quote/contracts", orderbook_url="https://open-api.bingx.com/openApi/swap/v2/quote/depth?symbol={native}&limit=100", ticker_url="https://open-api.bingx.com/openApi/swap/v2/quote/ticker?symbol={native}",trades_url="https://open-api.bingx.com/openApi/swap/v2/quote/trades?symbol={native}&limit=100"),
    AdapterSpec("phemex", "Phemex", "https://api.phemex.com/public/time", "wss://ws.phemex.com", {"id": 1, "method": "orderbook_p.subscribe", "params": ["{native}"]}, symbol_template="{base}USDT", market_metadata_url="https://api.phemex.com/public/products", orderbook_url="https://api.phemex.com/md/v2/orderbook?symbol={native}", ticker_url="https://api.phemex.com/md/v2/ticker/24hr?symbol={native}",trades_url="https://api.phemex.com/md/v2/trade?symbol={native}"),
]

REGISTRY = {spec.exchange_id: spec for spec in SPECS}


def get_adapter(exchange_id: str) -> AdapterSpec:
    try:
        return REGISTRY[exchange_id]
    except KeyError as exc:
        raise ValueError(f"unsupported exchange: {exchange_id}") from exc
