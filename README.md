# CEXLENS

[![CI](https://github.com/Volynskiy-Business/cexlens/actions/workflows/ci.yml/badge.svg)](https://github.com/Volynskiy-Business/cexlens/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**C**entralized **EX**change **L**atency **E**vidence & **N**etwork **S**tability

CEXLENS is an evidence-first benchmarking platform for comparing public futures-market connectivity from the computer where trading actually happens. It separates DNS, TCP, TLS, REST, and WebSocket observations, persists raw evidence in SQLite, and produces transparent rankings with confidence labels.

> CEXLENS never places orders, never requests API keys, and does not present ICMP ping as trading latency.

## MVP capabilities

- Consistent adapter contract for Binance, Bybit, OKX, Bitget, Gate.io, MEXC, KuCoin Futures, Kraken Futures, BingX, and Phemex.
- Async first/warm DNS, TCP, TLS, fresh/reused REST, heartbeat/reconnect WebSocket, route, and clock-quality diagnostics.
- Three-symbol WebSocket and order-book telemetry with spread, 5/10/25 bps depth, recent-trade frequency, volume, open interest, funding, and futures coverage.
- Robust p50/p75/p90/p95/p99 statistics, jitter, MAD, outlier count, failure rate, and confidence grading.
- SQLite evidence store with normalized entities and explicit error records.
- Multi-section HTML dashboard with local-time heatmaps, Markdown executive report with per-recommendation rationale, JSON summary, and layer-specific CSV exports retaining raw timing metadata.
- Resumable UTC/local campaign windows and aggregated multi-window reporting.
- Native Windows 11 workflow with PowerShell; Docker is not required.

## Quick start (PowerShell)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
cexlatency validate
cexlatency discover
cexlatency benchmark --config config/smoke.yaml --group priority
```

For a harmless preview:

```powershell
cexlatency --config config/haifa-7day.yaml benchmark --group priority --dry-run
```

Global options such as `--config` and `--json` precede the command. Generated data stays local under `data/` and `reports/generated/`.

## Commands

| Command | Purpose |
|---|---|
| `discover` | Show registered public endpoints and support status |
| `benchmark` | Run bounded one-shot probes for an exchange or group |
| `campaign` | Claim and execute resumable UTC/local campaign windows |
| `report` | Regenerate one run or aggregate a completed campaign |
| `status` | Inspect immutable campaign definition, windows, attempts, and run IDs |
| `retention` | Preview or explicitly apply the configured database retention policy |
| `compare` | Compare two score snapshots |
| `validate` | Deterministically validate config, registry, and safety state |

## Reading results responsibly

The fastest public REST endpoint is not necessarily the fastest order path or the best scalping venue. CEXLENS shows component metrics and evidence coverage. It refuses to declare a report winner when confidence is insufficient. Exchange timestamps provide *observed timestamp lag*, not exact one-way latency, unless local clock quality is independently verified.

## Development

```powershell
pytest
cexlatency --config config/smoke.yaml validate
cexlatency --config config/smoke.yaml benchmark --exchange binance --iterations 3 --ws-duration 5
```

See [Architecture](docs/ARCHITECTURE.md), [Methodology](docs/METHODOLOGY.md), [Scoring](docs/SCORING_MODEL.md), and [Windows setup](docs/WINDOWS_SETUP.md).
An evidence-labeled [example smoke benchmark](docs/EXAMPLE_BENCHMARK.md) is included.
The [specification traceability matrix](docs/SPEC_TRACEABILITY.md) distinguishes verified implementation evidence from the pending seven-day acceptance evidence.

## Status

The production-MVP implementation is complete, but a location-specific recommendation remains evidence-gated. Public endpoints can be geo-blocked, changed, or rate-limited, and the configured seven-day Haifa campaign has not yet elapsed. See [Known limitations](docs/LIMITATIONS.md) and [Acceptance report](docs/ACCEPTANCE_REPORT.md).

## License

MIT. Benchmark responsibly and comply with each venue's public API terms and local law.
