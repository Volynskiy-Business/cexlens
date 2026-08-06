import json

from cexlatency.json_logging import JsonEventLogger


def test_probe_error_has_required_structured_fields(tmp_path):
    path=tmp_path/"events.jsonl"; logger=JsonEventLogger(path)
    logger.probe_error("r1","binance","https://example.test","rest","HTTP_RATE_LIMIT","429",2,True)
    row=json.loads(path.read_text())
    assert {"timestamp","run_id","exchange","endpoint","probe_type","exception_type","retry_number","classification","recoverable"} <= set(row)
    assert row["classification"] == "HTTP_RATE_LIMIT"
