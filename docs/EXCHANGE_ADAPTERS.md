# Exchange adapters

| Exchange | Public REST | Public WebSocket | Default futures symbol form | MVP status |
|---|---|---|---|---|
| Binance | Yes | Yes | `BTCUSDT` | Declared, smoke-tested selectively |
| Bybit | Yes | Yes | `BTCUSDT` | Declared |
| OKX | Yes | Yes | `BTC-USDT-SWAP` | Declared |
| Bitget | Yes | Yes | `BTCUSDT` | Declared |
| Gate.io | Yes | Yes | `BTC_USDT` | Declared |
| MEXC | Yes | Yes | `BTC_USDT` | Declared |
| KuCoin Futures | Yes | Dynamic token required | `BTCUSDTM` | REST only / partial WS |
| Kraken Futures | Yes | Yes | `PI_XBTUSD` | Declared; canonical BTC alias needs follow-up |
| BingX | Yes | Yes | `BTC-USDT` | Declared |
| Phemex | Yes | Yes | `BTCUSDT` | Declared |

“Declared” does not mean universally reachable. The `discover` command reports configuration; live evidence belongs to individual run IDs. Endpoint changes must be fixture-tested before adapter edits are accepted.

