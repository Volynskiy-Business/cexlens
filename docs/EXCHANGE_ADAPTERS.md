# Exchange adapters

| Exchange | Public REST | Public WebSocket | Default futures symbol form | MVP status |
|---|---|---|---|---|
| Binance | Yes | Yes | `BTCUSDT` | Live smoke verified |
| Bybit | Yes | Yes | `BTCUSDT` | Live smoke verified |
| OKX | Yes | Yes | `BTC-USDT-SWAP` | Live smoke verified |
| Bitget | Yes | Yes | `BTCUSDT` | Live smoke verified |
| Gate.io | Yes | Yes | `BTC_USDT` | Live smoke verified |
| MEXC | Yes | Yes | `BTC_USDT` | Live smoke verified |
| KuCoin Futures | Yes | Dynamic public token | `XBTUSDTM` | Live smoke verified |
| Kraken Futures | Yes | Yes | `PI_XBTUSD` | Live smoke verified |
| BingX | Yes | Yes, gzip frames | `BTC-USDT` | Live smoke verified |
| Phemex | Yes | Yes | `BTCUSDT` | Live smoke verified |

Live verification refers to smoke run `30c515ac2072` from the user's connection on 2026-08-06: 10/10 REST, 10/10 WebSocket, and 30/30 order-book snapshots. It does not guarantee future or universal reachability. Every adapter has a sanitized fixture.
