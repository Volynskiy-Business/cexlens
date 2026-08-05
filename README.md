# CEXLENS

[![CI](https://github.com/Volynskiy-Business/cexlens/actions/workflows/ci.yml/badge.svg)](https://github.com/Volynskiy-Business/cexlens/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**C**entralized **EX**change **L**atency **E**vidence & **N**etwork **S**tability

CEXLENS is an evidence-first benchmarking platform for comparing public futures-market connectivity from the computer where trading actually happens. It separates DNS, TCP, TLS, REST, and WebSocket observations, persists raw evidence in SQLite, and produces transparent rankings with confidence labels.

> CEXLENS never places orders, never requests API keys, and does not present ICMP ping as trading latency.

## MVP capabilities

- Declarative registry for Binance, Bybit, OKX, Bitget, Gate.io, MEXC, KuCoin Futures, Kraken Futures, BingX, and Phemex.
- Async DNS, TCP, TLS, fresh-connection REST, reused-connection REST, and public WebSocket probes.
- Robust p50/p75/p90/p95/p99 statistics, jitter, MAD, outlier count, failure rate, and confidence grading.
- SQLite evidence store with normalized entities and explicit error records.
- HTML dashboard, Markdown executive report, JSON summary, and CSV exports.
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
| `campaign` | Execute the configured campaign unit; scheduling is documented separately |
| `report` | Regenerate reports from a persisted run |
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

## Status

This repository is an MVP. Public endpoints can be geo-blocked, changed, or rate-limited. KuCoin WebSocket requires dynamic public-token discovery and is explicitly marked partial. Market-depth normalization and seven-day scheduling remain roadmap work. See [Known limitations](docs/LIMITATIONS.md) and [Acceptance report](docs/ACCEPTANCE_REPORT.md).

## License

MIT. Benchmark responsibly and comply with each venue's public API terms and local law.
