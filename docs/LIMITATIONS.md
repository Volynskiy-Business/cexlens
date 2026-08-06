# Known limitations

- The full seven-day, six-window-per-day Haifa campaign has not yet elapsed, so no final venue recommendation is justified.
- Depth is approximate quote notional; contract multipliers and exchange-reported volume conventions can differ.
- Sequence-gap evaluation is disabled for snapshot-style channels without a guaranteed contiguous counter.
- Route diagnostics depend on `tracert`, `traceroute`, or `tracepath` availability and cannot locate a matching engine.
- Windows/WSL NTP offset is measured through `w32tm` when available. An offset outside ±100 ms is retained, warned about, and prevents a `VERIFIED` timestamp-quality label; otherwise synchronization state is recorded without an exact offset.
- Live integration checks depend on geography, exchange policy, DNS, and internet availability.
- Public market-data latency is not private order acknowledgement latency.
- Recent-trade frequency is a bounded snapshot estimate, not a full-day independently audited trade count.
