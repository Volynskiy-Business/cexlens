# MVP acceptance report

Status at repository bootstrap: **NOT READY** pending executed validation evidence and full seven-day campaign.

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
| Ten live adapters verified | Pending | Requires conservative live campaign |
| Full test suite passes | Verified | 11 tests passed on 2026-08-06 |
| Conservative live smoke run | Verified | Run `e356a31c5520`: REST 10/10 venues; WebSocket data 7/10 |
| Seven-day Haifa campaign | Pending | Requires elapsed observation windows |

The readiness gate remains `CEX_LATENCY_PLATFORM_MVP_NOT_READY` until mandatory live evidence is complete.
