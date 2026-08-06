from cexlatency.adapters import REGISTRY, get_adapter


def test_registry_has_required_priority_exchanges():
    assert len(REGISTRY) >= 10
    assert {"binance", "bybit", "okx", "bitget", "gate", "mexc", "kucoin", "kraken", "bingx", "phemex"} <= set(REGISTRY)


def test_symbol_mapping_and_subscription_are_adapter_local():
    okx = get_adapter("okx")
    assert okx.native_symbol("BTCUSDT") == "BTC-USDT-SWAP"
    assert okx.subscription("BTCUSDT")["args"][0]["instId"] == "BTC-USDT-SWAP"


def test_all_adapters_declare_market_quality_and_websocket_paths():
    for adapter in REGISTRY.values():
        assert adapter.orderbook_url
        assert adapter.ticker_url
        assert adapter.market_metadata_url
        assert adapter.websocket_supported
        assert callable(adapter.probe_rest)
        assert callable(adapter.probe_websocket)
        assert callable(adapter.subscribe_order_book)


def test_kucoin_dynamic_public_subscription():
    kucoin = get_adapter("kucoin")
    assert kucoin.ws_token_url.endswith("bullet-public")
    assert kucoin.subscription("BTCUSDT")["topic"] == "/contractMarket/level2Depth5:XBTUSDTM"


def test_exchange_specific_symbol_aliases():
    assert get_adapter("kraken").native_symbol("BTCUSDT") == "PI_XBTUSD"
    assert get_adapter("kraken").native_symbol("SOLUSDT") == "PF_SOLUSD"
    assert get_adapter("kucoin").native_symbol("ETHUSDT") == "ETHUSDTM"
