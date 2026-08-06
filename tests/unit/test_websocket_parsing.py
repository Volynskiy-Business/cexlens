from cexlatency.probes import _find_sequence, _find_timestamp


def test_timestamp_units_normalize_to_epoch_seconds():
    expected=1_720_000_000.0
    assert _find_timestamp({"E":1_720_000_000_000},("E",)) == expected
    assert _find_timestamp({"ts":1_720_000_000_000_000},("ts",)) == expected
    assert _find_timestamp({"timestamp":1_720_000_000_000_000_000},("timestamp",)) == expected


def test_nested_sequence_detection():
    assert _find_sequence({"data":{"sequence":"42"}}) == 42
    assert _find_sequence({"data":[{"version":99}]}) == 99
