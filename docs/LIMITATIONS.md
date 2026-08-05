# Known limitations

- KuCoin Futures WebSocket token discovery is not implemented.
- Kraken's XBT/BTC mapping needs adapter-specific alias support.
- Market-depth, spread, open-interest, funding, and instrument breadth are not yet normalized; scoring holds those dimensions neutral.
- The `campaign` command executes a campaign unit but does not yet persist a resumable seven-day scheduler state.
- Route diagnostics and NTP-offset detection are documented but not automated.
- WebSocket sequence gaps and reconnect recovery are represented in the model but need per-venue parsers.
- Live integration checks depend on geography, exchange policy, DNS, and internet availability.
- Public market-data latency is not private order acknowledgement latency.

