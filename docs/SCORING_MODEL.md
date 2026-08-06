# Scoring model

The overall profile is a configurable weighted sum of component scores: WebSocket performance 25%, REST p95 20%, tail stability 15%, reliability 10%, freshness 10%, market quality 10%, market breadth 5%, and accessibility 5%.

Latency dimensions use winsorized p10–p90 direction-aware normalization so one extreme venue cannot define the whole scale. Depth and volume use `log1p` before robust scaling. Missing core evidence reduces coverage and therefore the score. `INSUFFICIENT` evidence caps the overall score below a valid winner and sorts behind eligible evidence. Components and raw metrics are always emitted.

Confidence depends on successful sample count, success rate, observed windows, and timestamp quality. Labels are `HIGH`, `MEDIUM`, `LOW`, or `INSUFFICIENT`. The MVP intentionally avoids decimal-heavy claims: scores are presentation aids, while raw p50/p95/p99 and failure rate remain the evidence.

Market quality combines spread (50%), 10 bps depth (25%), and quote volume (25%). Market breadth uses exchange-reported futures instrument count. These values are comparative public evidence, not independent audits. The JSON report includes all nine required ranking views, including TCP network latency, WebSocket stability, freshness, majors, and an altcoin-breadth proxy.
