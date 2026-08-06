from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class ProbeConfig(BaseModel):
    iterations: int = Field(default=20, ge=1, le=500)
    timeout_seconds: float = Field(default=10, gt=0, le=60)
    websocket_observation_seconds: int = Field(default=600, ge=1, le=3600)
    bounded_concurrency: int = Field(default=5, ge=1, le=20)
    per_exchange_concurrency: int = Field(default=1, ge=1, le=5)
    jitter_ms: int = Field(default=250, ge=0, le=5000)
    warmup_iterations: int = Field(default=1, ge=0, le=10)
    market_quality: bool = True
    route_diagnostics: bool = False
    route_max_hops: int = Field(default=20, ge=1, le=64)


class CampaignConfig(BaseModel):
    name: str = "haifa-home-baseline"
    timezone: str = "Asia/Jerusalem"
    duration_days: int = Field(default=7, ge=1, le=90)
    windows_local: list[str] = ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00"]
    window_grace_minutes: int = Field(default=30, ge=1, le=1440)
    window_lease_minutes: int = Field(default=180, ge=30, le=720)

    @field_validator("windows_local")
    @classmethod
    def valid_windows(cls, values: list[str]) -> list[str]:
        for value in values:
            parts = value.split(":")
            if len(parts) != 2 or not all(p.isdigit() for p in parts) or int(parts[0]) > 23 or int(parts[1]) > 59:
                raise ValueError(f"invalid HH:MM window: {value}")
        return values


class ScoringConfig(BaseModel):
    profile: str = "manual-futures-scalping"
    weights: dict[str, float] = {
        "websocket": 0.25,
        "rest_p95": 0.20,
        "tail_stability": 0.15,
        "reliability": 0.10,
        "freshness": 0.10,
        "market_quality": 0.10,
        "market_breadth": 0.05,
        "accessibility": 0.05,
    }

    @model_validator(mode="after")
    def weights_sum(self) -> "ScoringConfig":
        if abs(sum(self.weights.values()) - 1.0) > 1e-6:
            raise ValueError("scoring weights must sum to 1.0")
        return self


class AppConfig(BaseModel):
    campaign: CampaignConfig = CampaignConfig()
    exchanges: dict[str, list[str]] = {"priority": ["binance", "bybit", "okx", "bitget", "gate", "mexc", "kucoin", "kraken", "bingx", "phemex"]}
    symbols: dict[str, list[str]] = {"major": ["BTCUSDT", "ETHUSDT", "SOLUSDT"]}
    probes: ProbeConfig = ProbeConfig()
    scoring: ScoringConfig = ScoringConfig()
    storage_path: str = "data/cexlatency.db"
    report_directory: str = "reports/generated"

    def selected_exchanges(self, group: str = "priority") -> list[str]:
        if group not in self.exchanges:
            raise ValueError(f"unknown exchange group: {group}")
        return self.exchanges[group]

    def benchmark_symbols(self) -> list[str]:
        """Return every configured symbol once, preserving YAML group order."""
        return list(dict.fromkeys(symbol for group in self.symbols.values() for symbol in group))


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    raw: dict[str, Any] = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return AppConfig.model_validate(raw)
