# Example benchmark output

Initial smoke run `7aeeef0bd649`, followed by post-fix verification run `e356a31c5520`, was executed from the local machine in Haifa on 2026-08-06 with one reused and one fresh REST request per venue plus a three-second WebSocket observation.

- All 10 configured venues returned successful public REST responses (20/20 requests).
- Seven WebSocket endpoints delivered market-data messages during the post-fix window (Binance, Bybit, OKX, Bitget, Gate.io, MEXC, and Kraken Futures).
- KuCoin WebSocket remained explicitly unsupported because dynamic public-token discovery is pending.
- BingX and Phemex WebSocket handshakes did not yield usable market data in this run.
- Every ranking was `INSUFFICIENT`, as required: two REST samples and a three-second stream cannot support a venue recommendation.

The initial run exposed and led to a fix for observation-window timeout classification; the second run verified the correction. Numeric rankings are intentionally not reproduced as decision evidence. The complete seven-day campaign must use new run IDs.

Example command:

```powershell
cexlatency --config config/smoke.yaml benchmark --group priority
```

Expected result shape:

```text
Run <RUN_ID> complete
1. <exchange> <score> (INSUFFICIENT)
...
10. <exchange> <score> (INSUFFICIENT)
```
