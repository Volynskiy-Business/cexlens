import argparse

import pytest

from cexlatency.cli import parse_duration, parser
from cexlatency.runner import _continue_rest_probing


@pytest.mark.parametrize(("value","expected"), [("30s",30),("10m",600),("2h",7200),("1.5m",90)])
def test_parse_duration(value, expected):
    assert parse_duration(value) == expected


@pytest.mark.parametrize("value", ["10", "abc", "0s", "8d"])
def test_parse_duration_rejects_invalid_values(value):
    with pytest.raises(argparse.ArgumentTypeError): parse_duration(value)


def test_config_is_accepted_before_or_after_command():
    assert parser().parse_args(["--config","a.yaml","validate"]).config == "a.yaml"
    assert parser().parse_args(["validate","--config","b.yaml"]).config == "b.yaml"
    assert parser().parse_args(["status","--campaign","c"]).campaign == "c"
    assert parser().parse_args(["retention","--apply"]).apply is True


def test_fixed_duration_has_no_hidden_500_iteration_cutoff():
    assert _continue_rest_probing(500,1,1000.0,999.0)
    assert not _continue_rest_probing(500,1,1000.0,1000.0)
