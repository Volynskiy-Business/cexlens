# Measurement methodology

Measurements originate on the local host. DNS time covers resolver completion, TCP time covers connection establishment, TLS time includes verified certificate negotiation, REST reports time to first byte and total response time, and WebSocket reports handshake/first-message/inter-arrival behavior.

Fresh and reused HTTP connections are measured separately. The former includes setup overhead; the latter approximates steady-state public API use. All durations use the monotonic clock. UTC wall time is used only for event-time comparison and audit timestamps.

Observed timestamp lag equals local UTC receive time minus the exchange event timestamp. Clock skew can dominate it, so the metric remains `UNKNOWN` quality until an independent OS/NTP check exists. It is never described as true one-way latency.

Campaigns use bounded concurrency, one exchange coroutine at a time per venue, randomized inter-probe jitter, conservative public endpoints, and short payloads. A seven-day conclusion requires all configured time windows; a smoke run only validates mechanics.

Each venue receives a separately labeled REST warm-up before measured fresh/reused iterations. Warm-up samples remain auditable in SQLite but are excluded from distributions and scoring.

Order-book snapshots are normalized into best bid/ask, spread in basis points, and approximate quote notional within 5, 10, and 25 bps of mid. Contract-size conventions differ by venue; depth, volume, open interest, and funding are labeled exchange-provided and are not independently audited. Three canonical symbols are collected per venue.

WebSocket sessions measure handshake, subscription acknowledgement where explicit, first message, heartbeat RTT, inter-arrival distribution, stale periods, malformed and duplicate messages, and a controlled reconnect. Sequence gaps are evaluated only when the selected channel declares a contiguous counter.

Route diagnostics are diagnostic evidence and cannot identify a matching-engine location. ICMP ping is intentionally absent from the ranking.
