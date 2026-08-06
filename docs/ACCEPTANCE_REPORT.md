# MVP acceptance report

Implementation status: production-MVP feature set verified; location-specific acceptance remains **NOT READY** pending the full seven-day campaign.

| Criterion | State | Evidence |
|---|---|---|
| 10 priority adapters | Implemented | Registry and adapter tests |
| Three canonical futures symbols | Implemented | YAML config and market contract |
| Separate REST and WebSocket measurements | Implemented | Probe models and persistence |
| p50/p95/p99, jitter, failures | Implemented | Unit tests |
| SQLite persistence | Implemented | Storage integration test |
| HTML/Markdown/CSV/JSON | Implemented | Reporting integration test |
| Transparent scoring and missing-data penalty | Implemented | Scoring tests |
| No key / no live order | Verified by design | No credential or order interface exists |
| Windows 11 native support | Documented | Windows setup guide |
| Ten live adapters verified | Verified | Run `03bad502ba00`: REST 20/20; WS 30/30; order books and trade-frequency samples 30/30 |
| Full test suite passes | Verified | 80 passed, 2 opt-in live tests skipped; opt-in live suite 2/2 passed |
| Conservative live smoke run | Verified | Run `03bad502ba00`, zero recorded probe errors |
| Resumable sample campaign | Verified | `haifa-smoke-acceptance`: one window completed as run `6672d3066fe3`; aggregate report generated |
| Seven-day Haifa campaign | Pending | Requires elapsed observation windows |

The readiness gate remains `CEX_LATENCY_PLATFORM_MVP_NOT_READY` until all 42 scheduled windows complete and the aggregate recommendation is generated. This is an evidence-duration gate, not an implementation failure. `cexlatency acceptance --config config/haifa-7day.yaml --campaign haifa-home-baseline` enforces this gate with a non-zero exit code while any required window, normalized evidence layer, reproducibility field, report artifact, or eligible recommendation is missing.
