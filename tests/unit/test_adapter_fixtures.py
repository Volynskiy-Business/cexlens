import json
from pathlib import Path

import pytest

from cexlatency.market_quality import calculate_depth, extract_book


FIXTURES=Path(__file__).parents[1]/"fixtures"


@pytest.mark.parametrize("exchange_id", ["binance","bybit","okx","bitget","gate","mexc","kucoin","kraken","bingx","phemex"])
def test_sanitized_orderbook_fixture_parses(exchange_id):
    payload=json.loads((FIXTURES/f"{exchange_id}_orderbook.json").read_text())
    bids,asks=extract_book(exchange_id,payload)
    result=calculate_depth(bids,asks)
    assert result["best_bid"] == 100.0
    assert result["best_ask"] == 100.1
    assert result["bid_depth_25bps"] == 200.0
    assert result["ask_depth_25bps"] == pytest.approx(300.3)
