import pytest
from pydantic import ValidationError

from cexlatency.config import AppConfig, CampaignConfig, RetentionConfig, ScoringConfig


def test_default_config_has_ten_exchanges_and_three_symbols():
    config = AppConfig()
    assert len(config.exchanges["priority"]) == 10
    assert config.symbols["major"] == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


def test_benchmark_symbols_flattens_configured_groups_without_duplicates():
    config=AppConfig(symbols={"major":["BTCUSDT","ETHUSDT"],"mid_cap":["ETHUSDT","LINKUSDT"]})
    assert config.benchmark_symbols() == ["BTCUSDT","ETHUSDT","LINKUSDT"]


def test_weights_must_sum_to_one():
    with pytest.raises(ValidationError):
        ScoringConfig(weights={"rest_p95": 0.4})


def test_time_window_validation():
    with pytest.raises(ValidationError):
        CampaignConfig(windows_local=["25:99"])


def test_timezone_validation_is_deterministic():
    with pytest.raises(ValidationError,match="unknown IANA timezone"):
        CampaignConfig(timezone="Mars/Olympus")


def test_retention_is_disabled_by_default_and_bounded():
    assert RetentionConfig().benchmark_days is None
    with pytest.raises(ValidationError): RetentionConfig(benchmark_days=0)
