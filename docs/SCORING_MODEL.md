# Scoring model

The overall profile is a configurable weighted sum of component scores: WebSocket performance 25%, REST p95 20%, tail stability 15%, reliability 10%, freshness 10%, market quality 10%, market breadth 5%, and accessibility 5%.

Latency dimensions use winsorized p10–p90 direction-aware normalization so one extreme venue cannot define the whole scale. Depth, volume, and trade frequency use `log1p` before robust scaling. Any missing core evidence forces `INSUFFICIENT`; coverage also scales the score, which is capped below a valid winner and sorted behind eligible evidence. Components and raw metrics are always emitted.

Confidence depends on successful sample count, combined network/REST/WebSocket/market success, endpoint coverage, actual WebSocket observation duration, observed windows, cross-window REST p95 consistency, and timestamp quality. Cross-window coefficient of variation above 0.5 forces `LOW`; above 1.0 is `INSUFFICIENT`. Labels are `HIGH`, `MEDIUM`, `LOW`, or `INSUFFICIENT`. The MVP intentionally avoids decimal-heavy claims: scores are presentation aids, while raw p50/p95/p99 and failure rate remain the evidence.

Each ranked row also exposes an evidence-aware `behavior_label`: `fast_but_unstable`, `stable_but_slower`, `consistently_poor`, `balanced`, or `insufficient_evidence`. The labels use the normalized REST p95 and tail-stability components with explicit 70/40 thresholds.

WebSocket performance combines first-valid-message speed (40%) and an instability penalty (60%) derived from failed sessions, disconnect/recovery failures, malformed messages, sequence gaps, duplicates, and stale periods. Market quality combines spread (40%), 10 bps depth (20%), quote volume (20%), and recent-trade frequency (20%). Market breadth uses exchange-reported futures instrument count. These values are comparative public evidence, not independent audits. The JSON report includes all nine required ranking views, including TCP network latency, WebSocket stability, freshness, majors, and an altcoin-breadth proxy.
