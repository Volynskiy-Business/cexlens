import pytest

from cexlatency.market_quality import calculate_depth, extract_book, extract_market_count, extract_ticker, extract_trade_frequency


def test_binance_book_and_depth_bands():
    bids, asks = extract_book("binance", {"bids": [["100", "2"], ["99.9", "3"]], "asks": [["100.1", "1"], ["100.2", "4"]]})
    result = calculate_depth(bids, asks)
    assert result["best_bid"] == 100
    assert result["best_ask"] == 100.1
    assert result["spread_bps"] == pytest.approx(9.995, rel=1e-3)
    assert result["bid_depth_25bps"] == pytest.approx(499.7)
    assert result["ask_depth_25bps"] == pytest.approx(500.9)


def test_gate_object_levels_are_normalized():
    bids, asks = extract_book("gate", {"bids": [{"p": "10", "s": 5}], "asks": [{"p": "11", "s": 2}]})
    assert bids == [(10.0, 5.0)]
    assert asks == [(11.0, 2.0)]


def test_bybit_ticker_and_market_count():
    ticker = extract_ticker("bybit", {"result": {"list": [{"volume24h": "12", "turnover24h": "300", "openInterest": "7", "fundingRate": "0.0001"}]}}, "BTCUSDT")
    assert ticker == {"volume_24h": 12.0, "quote_volume_24h": 300.0, "open_interest": 7.0, "funding_rate": 0.0001}
    assert extract_market_count("bybit", {"result": {"list": [{}, {}, {}]}}) == 3


def test_crossed_book_is_rejected():
    with pytest.raises(ValueError, match="crossed"):
        calculate_depth([(101, 1)], [(100, 1)])


@pytest.mark.parametrize(("exchange","payload"),[
    ("binance",[{"time":1_720_000_000_000},{"time":1_720_000_001_000}]),
    ("bybit",{"result":{"list":[{"time":"1720000000000"},{"time":"1720000001000"}]}}),
    ("okx",{"data":[{"ts":"1720000000000"},{"ts":"1720000001000"}]}),
    ("bitget",{"data":[{"ts":"1720000000000"},{"ts":"1720000001000"}]}),
    ("gate",[{"create_time":1_720_000_000.0},{"create_time":1_720_000_001.0}]),
    ("mexc",{"data":[{"t":1_720_000_000_000},{"t":1_720_000_001_000}]}),
    ("kucoin",{"data":[{"ts":1_720_000_000_000_000_000},{"ts":1_720_000_001_000_000_000}]}),
    ("kraken",{"history":[{"time":"2024-07-03T09:46:40Z"},{"time":"2024-07-03T09:46:41Z"}]}),
    ("bingx",{"data":[{"time":1_720_000_000_000},{"time":1_720_000_001_000}]}),
    ("phemex",{"result":{"trades_p":[[1_720_000_000_000_000_000],[1_720_000_001_000_000_000]]}}),
])
def test_trade_frequency_parsing(exchange,payload):
    result=extract_trade_frequency(exchange,payload)
    assert result["trade_count_sample"] == 2
    assert result["trade_sample_span_seconds"] == pytest.approx(1)
    assert result["trade_frequency_hz"] == pytest.approx(1)
