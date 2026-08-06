# Example benchmark output

Current end-to-end smoke run `03bad502ba00` was executed from the local machine in Haifa on 2026-08-06 with first/warm DNS, separate REST/WebSocket TCP and TLS, one reused and one fresh REST request per venue, three order-book and recent-trade symbols, and per-symbol WebSocket observation plus reconnect-to-first-data recovery.

- All 10 configured venues returned successful public REST responses (20/20 requests).
- All 30 WebSocket sessions (10 venues × BTC/ETH/SOL) delivered market-data messages; reconnect failures remain explicit session metrics.
- All 30 order-book snapshots and all 30 recent-trade samples parsed successfully.
- Registry persistence contained 10 exchanges, public REST/WebSocket/market/trade endpoints, and 30 canonical/native symbol mappings.
- No probe error was recorded.
- Every ranking was `INSUFFICIENT`, as required: two REST samples and three-second streams cannot support a venue recommendation.
- The report includes `metric_statistics.csv` with count, success/failure, median, p75/p90/p95/p99, dispersion, jitter, and outlier statistics for the available DNS/TCP/TLS/REST/WebSocket/market layers.

Numeric rankings are intentionally not reproduced as decision evidence because every venue remained `INSUFFICIENT` after one short window. The complete seven-day campaign must use new run IDs.

The scheduler itself was validated by campaign `haifa-smoke-acceptance`: its due window was atomically claimed, completed as run `6672d3066fe3`, persisted with `COMPLETED` status and one attempt, and regenerated as an aggregate campaign dashboard. Evidence counts were again REST 20/20, WebSocket 10/10, order books 30/30, errors 0.

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
