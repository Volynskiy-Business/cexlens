import pytest
from pydantic import ValidationError

from cexlatency.config import AppConfig, CampaignConfig, ScoringConfig


def test_default_config_has_ten_exchanges_and_three_symbols():
    config = AppConfig()
    assert len(config.exchanges["priority"]) == 10
    assert config.symbols["major"] == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


def test_weights_must_sum_to_one():
    with pytest.raises(ValidationError):
        ScoringConfig(weights={"rest_p95": 0.4})


def test_time_window_validation():
    with pytest.raises(ValidationError):
        CampaignConfig(windows_local=["25:99"])

