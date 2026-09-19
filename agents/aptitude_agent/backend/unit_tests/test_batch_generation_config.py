"""BATCH_GENERATION_MAX_ATTEMPTS defaults and stays bounded to 1-3."""
import importlib
import os

import pytest


@pytest.fixture
def reload_config(monkeypatch):
    def load(value=None):
        if value is None:
            monkeypatch.delenv("BATCH_GENERATION_MAX_ATTEMPTS", raising=False)
        else:
            monkeypatch.setenv("BATCH_GENERATION_MAX_ATTEMPTS", value)
        from backend.app import config
        return importlib.reload(config).Config
    return load


def test_default_is_three_not_two(reload_config):
    # A batch discards every question and fully regenerates if even one item
    # fails content validation, so a low attempt count lets a single unlucky
    # topic draw exhaust retries and 503 the whole test. Production had this
    # set to 2 when that happened; the code-level default must not regress
    # back to it.
    assert reload_config(None).BATCH_GENERATION_MAX_ATTEMPTS == 3


@pytest.mark.parametrize("raw,expected", [("1",1), ("2",2), ("3",3), ("5",3), ("0",1), ("-1",1)])
def test_an_explicit_value_stays_within_one_to_three(reload_config, raw, expected):
    assert reload_config(raw).BATCH_GENERATION_MAX_ATTEMPTS == expected
