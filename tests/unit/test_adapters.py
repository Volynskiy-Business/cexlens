from cexlatency.adapters import REGISTRY, get_adapter


def test_registry_has_required_priority_exchanges():
    assert len(REGISTRY) >= 10
    assert {"binance", "bybit", "okx", "bitget", "gate", "mexc", "kucoin", "kraken", "bingx", "phemex"} <= set(REGISTRY)


def test_symbol_mapping_and_subscription_are_adapter_local():
    okx = get_adapter("okx")
    assert okx.native_symbol("BTCUSDT") == "BTC-USDT-SWAP"
    assert okx.subscription("BTCUSDT")["args"][0]["instId"] == "BTC-USDT-SWAP"

