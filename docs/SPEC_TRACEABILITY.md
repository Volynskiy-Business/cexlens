# Specification traceability

This matrix maps the production specification to executable or persisted evidence. `Verified` means the current repository contains direct evidence; `Pending evidence` is never treated as implementation success.

| Specification area | State | Authoritative evidence |
|---|---|---|
| Public-only safety; no keys or orders | Verified | `src/cexlatency/` contains no credential or order interface; `cexlatency validate` emits the safety state |
| Configurable adapter contract and 10 priority venues | Verified | `src/cexlatency/adapters.py`; registry, fixture, and opt-in live tests |
| DNS, TCP, TLS, REST fresh/reuse measurements | Verified | `src/cexlatency/probes.py`; normalized `probe_samples`; live run evidence |
| REST timing provenance and server timestamps | Verified | Per-sample `metadata_json` contains monotonic boundaries, UTC receive time, rate-limit headers, and exchange timestamp when present |
| Per-symbol WebSocket timing and stability | Verified | `websocket_sessions` records handshake, acknowledgement, first data, heartbeat, intervals, anomalies, actual observation duration, and reconnect-to-first-data |
| BTC, ETH, and SOL futures market quality | Verified | `config/haifa-7day.yaml`; order-book fixtures and live 30/30 market snapshots in run `03bad502ba00` |
| Volume, open interest, funding, spread, 5/10/25 bps depth, trades, breadth | Verified | `src/cexlatency/market_quality.py`; `orderbook_quality_summary`; CSV/JSON report exports |
| Safe route diagnostics and route-change evidence | Verified | `src/cexlatency/diagnostics.py`; structured route summaries and fingerprints |
| Seven days × six local windows, UTC persistence | Verified implementation | Campaign schedule/lease/resume tests; active `haifa-home-baseline` definition contains 42 immutable windows |
| Bounded concurrency, warm-up, randomized jitter, fixed duration | Verified | `src/cexlatency/runner.py`; deterministic config and duration-loop tests |
| Reproducibility metadata | Verified | Git SHA, version, config snapshot, anonymized host, Windows physical/runtime interface, ISP, timezone, clock status, adapters, endpoints, and markets persisted in SQLite |
| Full robust statistics | Verified | `src/cexlatency/metrics.py`; p50/p75/p90/p95/p99, MAD, CV, jitter, outliers, success/failure tests |
| Nine transparent rankings and fail-closed scoring | Verified | `src/cexlatency/scoring.py`, `src/cexlatency/reporting.py`; raw metrics, components, behavior labels, evidence coverage, confidence |
| Confidence uses duration and cross-window consistency | Verified | Sample/success/endpoint coverage, actual WS seconds, windows, REST p95 CV, timestamp quality; unit tests |
| Normalized SQLite model and retention | Verified | All minimum entities in `src/cexlatency/storage.py`; preview/apply retention tests preserve campaign runs |
| Production CLI behavior | Verified | discover, benchmark, campaign, status, report, compare, retention, validate; dry-run/JSON/resume/cancellation paths |
| HTML, Markdown, CSV, JSON reporting | Verified | Reporting integration test and generated run artifacts; local-time heatmap and per-recommendation rationale |
| Structured logs and explicit errors | Verified | `src/cexlatency/json_logging.py`; `errors` table; logging tests |
| Native Windows setup and supervision | Verified | Windows CI 3.12/3.13; `scripts/cexlatency.ps1`; battery-safe, wake-enabled Task Scheduler watchdog |
| Complete documentation set | Verified | README plus architecture, methodology, adapters, scoring, Windows, quality, limitations, roadmap, example, and acceptance documents |
| Complete seven-day Haifa result | Pending evidence | The real 42-window campaign must finish before the final recommendation or READY gate is allowed |

## Acceptance criteria

Criteria 1–13 and 15 in section 15.4 are directly verified by tests, live smoke evidence, generated artifacts, CI, and Windows deployment. Criterion 14 remains pending until all 42 location-specific windows complete and an aggregate campaign report is regenerated. Until then the only valid gate is `CEX_LATENCY_PLATFORM_MVP_NOT_READY`.

## Repeatable validation

```powershell
pytest
cexlatency --config config/smoke.yaml validate
cexlatency --config config/haifa-7day.yaml status --campaign haifa-home-baseline
cexlatency --config config/haifa-7day.yaml report --campaign haifa-home-baseline
```

The final report command is intentionally expected to remain evidence-gated until at least one campaign window exists and is only acceptance-complete after all 42 scheduled windows are `COMPLETED`.
