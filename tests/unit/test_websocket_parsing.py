import ssl

import httpx
import pytest

from cexlatency.adapters import AdapterSpec
from cexlatency.probes import _close_writer, _find_sequence, _find_timestamp, probe_rest


def test_timestamp_units_normalize_to_epoch_seconds():
    expected=1_720_000_000.0
    assert _find_timestamp({"E":1_720_000_000_000},("E",)) == expected
    assert _find_timestamp({"ts":1_720_000_000_000_000},("ts",)) == expected
    assert _find_timestamp({"timestamp":1_720_000_000_000_000_000},("timestamp",)) == expected
    assert _find_timestamp({"timeSecond":"1720000000"},("timeSecond",)) == expected


def test_nested_sequence_detection():
    assert _find_sequence({"data":{"sequence":"42"}}) == 42


@pytest.mark.asyncio
async def test_stream_close_notify_does_not_invalidate_completed_probe():
    class Writer:
        def __init__(self): self.closed=False
        def close(self): self.closed=True
        async def wait_closed(self): raise ssl.SSLError("application data after close notify")
    writer=Writer()
    await _close_writer(writer)
    assert writer.closed
    assert _find_sequence({"data":[{"version":99}]}) == 99


@pytest.mark.asyncio
async def test_rest_probe_records_server_and_local_timing_evidence():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200,json={"serverTime":1_720_000_000_000},request=request)
    adapter=AdapterSpec("test","Test","https://example.test/time",None)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        sample=await probe_rest("run",adapter,client,1)
    assert sample.started_at.endswith("+00:00")
    assert sample.metadata["server_timestamp_utc"] == "2024-07-03T09:46:40+00:00"
    assert sample.metadata["server_timestamp_quality"] == "EXCHANGE_PROVIDED"
    assert sample.metadata["local_monotonic_ended_ns"] >= sample.metadata["local_monotonic_started_ns"]
