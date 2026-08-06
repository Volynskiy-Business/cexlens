# Example benchmark output

Current end-to-end smoke run `30c515ac2072` was executed from the local machine in Haifa on 2026-08-06 with first/warm DNS, TCP, TLS, one reused and one fresh REST request per venue, three order-book symbols, and WebSocket observation plus reconnect.

- All 10 configured venues returned successful public REST responses (20/20 requests).
- All 10 WebSocket endpoints delivered market-data messages and a reconnect measurement.
- All 30 order-book snapshots (10 venues × BTC/ETH/SOL) parsed successfully.
- Registry persistence contained 10 exchanges, 30 public endpoints, and 30 canonical/native symbol mappings.
- No probe error was recorded.
- Every ranking was `INSUFFICIENT`, as required: two REST samples and a three-second stream cannot support a venue recommendation.

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
