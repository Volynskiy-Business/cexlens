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
    binance=next(result for result in results if result.exchange_id=="binance")
    assert binance.metadata["server_timestamp_quality"] == "EXCHANGE_PROVIDED"
    assert binance.metadata["local_monotonic_ended_ns"] >= binance.metadata["local_monotonic_started_ns"]


@pytest.mark.asyncio
@pytest.mark.live
async def test_websocket_market_data_and_reconnect_path():
    adapter=get_adapter("binance")
    first=await probe_websocket("live-test",adapter,"BTCUSDT",2,10)
    second=await probe_websocket("live-test",adapter,"BTCUSDT",2,10)
    assert first.success and first.messages>0
    assert second.success and second.messages>0
    assert first.ack_ms is not None and second.ack_ms is not None
    assert first.reconnect_ms is not None and second.reconnect_ms is not None
    assert 1.5 <= first.observation_seconds <= 2.5
    assert 1.5 <= second.observation_seconds <= 2.5
