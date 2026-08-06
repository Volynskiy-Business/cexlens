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

Live verification refers to smoke run `03bad502ba00` from the user's connection on 2026-08-06: 20/20 measured REST requests, 30/30 per-symbol WebSocket sessions, 30/30 order-book snapshots, and 30/30 recent-trade frequency samples. It does not guarantee future or universal reachability. Every adapter has a sanitized fixture.
