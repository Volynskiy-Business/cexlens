# Scoring model

The overall profile is a configurable weighted sum of component scores: WebSocket performance 25%, REST p95 20%, tail stability 15%, reliability 10%, freshness 10%, market quality 10%, market breadth 5%, and accessibility 5%.

Latency dimensions use within-run min/max direction-aware normalization. Missing core evidence reduces coverage and therefore the score. `INSUFFICIENT` evidence caps the overall score below a valid winner. Components and raw metrics are always emitted.

Confidence depends on successful sample count, success rate, observed windows, and timestamp quality. Labels are `HIGH`, `MEDIUM`, `LOW`, or `INSUFFICIENT`. The MVP intentionally avoids decimal-heavy claims: scores are presentation aids, while raw p50/p95/p99 and failure rate remain the evidence.

Market-quality and breadth components remain neutral until normalized public depth and instrument-count telemetry is collected. Reports disclose this rather than turning missing evidence into a fabricated advantage.

