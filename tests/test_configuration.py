"""Tests for :mod:`pyisy.configuration`."""

from __future__ import annotations

import pytest

from pyisy.configuration import Configuration
from pyisy.exceptions import ISYResponseParseError


def test_parse_real_eisy_config(config_xml: str) -> None:
    config = Configuration(xml=config_xml)

    assert config["model"], "model should be populated from <product><desc>"
    assert config["uuid"], "uuid should be populated"
    assert config["firmware"], "firmware should be populated"
    # Real eisy does not advertise as ISY 994.
    assert not config["model"].startswith("ISY 994")
    # Booleans for variables / node defs are coerced from XML "true"/"false".
    assert isinstance(config["variables"], bool)
    assert isinstance(config["nodedefs"], bool)


def test_features_indexed_by_id_and_description(config_xml: str) -> None:
    config = Configuration(xml=config_xml)

    feature_ids = [k for k in config if isinstance(k, str) and k.isdigit()]
    assert feature_ids, "expected at least one numeric feature id"
    for fid in feature_ids:
        assert isinstance(config[fid], bool)


def test_invalid_xml_raises_parse_error() -> None:
    with pytest.raises(ISYResponseParseError):
        Configuration(xml="<not really xml")


def test_snapshot_known_keys(config_xml: str, snapshot) -> None:
    """Snapshot the stable, non-uuid subset of configuration keys.

    uuid/firmware/name are device-specific, so we exclude them; the goal is to
    catch parsing regressions for module/feature flags.
    """
    config = Configuration(xml=config_xml)
    sanitized = {k: v for k, v in config.items() if k not in {"uuid", "firmware", "name"}}
    assert sanitized == snapshot
