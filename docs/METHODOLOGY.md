# Measurement methodology

Measurements originate on the local host. DNS time covers resolver completion, TCP time covers connection establishment, TLS time includes verified certificate negotiation, REST reports time to first byte and total response time, and WebSocket reports handshake/first-message/inter-arrival behavior.

Fresh and reused HTTP connections are measured separately. The former includes setup overhead; the latter approximates steady-state public API use. All durations use the monotonic clock. UTC wall time is used only for event-time comparison and audit timestamps.

Observed timestamp lag equals local UTC receive time minus the exchange event timestamp. Clock skew can dominate it. A synchronized clock without a measured offset is labeled `SYNCHRONIZED_OFFSET_UNKNOWN`, not `VERIFIED`; the metric is never described as true one-way latency without a bounded offset measurement.

Campaigns use both a global concurrency bound and a configurable per-exchange semaphore, randomized inter-probe jitter, conservative public endpoints, and short payloads. A seven-day conclusion requires all configured time windows; a smoke run only validates mechanics.

Each venue receives a separately labeled REST warm-up before measured fresh/reused iterations. Warm-up samples remain auditable in SQLite but are excluded from distributions and scoring.

Order-book snapshots are normalized into best bid/ask, spread in basis points, and approximate quote notional within 5, 10, and 25 bps of mid. Recent public trades provide a bounded sample count, sample span, and observed trades per second. This is a recent-sample frequency estimate, not a 24-hour average. Contract-size conventions differ by venue; depth, volume, open interest, funding, and trades are exchange-provided and are not independently audited. Every configured symbol group is flattened without duplicates; the default campaign collects BTCUSDT, ETHUSDT, and SOLUSDT.

WebSocket sessions run separately for every configured symbol and measure handshake, subscription acknowledgement where explicit, first valid market-data message, heartbeat RTT, mean/median/p95 inter-arrival distribution, stale periods, malformed and duplicate messages, and controlled reconnect-to-first-data recovery. Sequence gaps are evaluated only when the selected channel declares a contiguous counter.

Route diagnostics persist raw output plus hop count, responding-hop count, maximum visible latency, largest hop-to-hop increase, a conservative suspected-bottleneck flag, and a route fingerprint for change detection. These remain diagnostic evidence and cannot identify a matching-engine location. ICMP ping is intentionally absent from the ranking.
