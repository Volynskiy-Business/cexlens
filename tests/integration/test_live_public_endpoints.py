import os

import httpx
import pytest

from cexlatency.adapters import REGISTRY, get_adapter
from cexlatency.probes import probe_rest, probe_websocket


pytestmark = pytest.mark.skipif(os.getenv("CEXLATENCY_LIVE") != "1", reason="set CEXLATENCY_LIVE=1 for conservative public-endpoint checks")


@pytest.mark.asyncio
@pytest.mark.live
async def test_all_registered_rest_endpoints_once():
    async with httpx.AsyncClient(timeout=12,follow_redirects=True) as client:
        results=[await probe_rest("live-test",adapter,client,12) for adapter in REGISTRY.values()]
    failures=[f"{r.exchange_id}:{r.status_code}:{r.error_class}" for r in results if not r.success]
    assert not failures, failures


@pytest.mark.asyncio
@pytest.mark.live
async def test_websocket_market_data_and_reconnect_path():
    adapter=get_adapter("binance")
    first=await probe_websocket("live-test",adapter,"BTCUSDT",2,10)
    second=await probe_websocket("live-test",adapter,"BTCUSDT",2,10)
    assert first.success and first.messages>0
    assert second.success and second.messages>0
