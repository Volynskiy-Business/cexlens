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

## Current-commit production preflight

Run `1d0119f1ff4c` was executed on commit `eff5d1a2f3ebee1ade4b48ca21b28ec96bcf1626` after Windows/WSL clock and watchdog hardening. With intentionally short one-second WebSocket windows it produced REST 20/20, DNS/TCP/TLS 95/95, market quality 30/30, and WebSocket 29/30. Gate/SOL did not deliver a valid message inside that deliberately abbreviated second and was persisted as `INSUFFICIENT_SAMPLE`; no evidence was silently promoted. The host record captured the physical Intel Ethernet interface, ISP label, `time.nist.gov` clock source, and a measured offset near −171 ms as `MEASURED_OFFSET_OUT_OF_BOUNDS`. All eight report artifact types were generated. This preflight validates the current integrated mechanics but is not decision evidence and does not substitute for the 600-second × 42-window production campaign.

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
