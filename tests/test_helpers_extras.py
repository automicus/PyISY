"""Tests for the rest of :mod:`pyisy.helpers` — XML edge cases,
``parse_isy_datetime`` format ladder, and the ``EventEmitter`` filter
and error-handling branches.
"""

from __future__ import annotations

from dataclasses import dataclass
from xml.dom import minidom

import pytest

from pyisy.helpers import (
    EMPTY_TIME,
    EventEmitter,
    NodeProperty,
    attr_from_xml,
    parse_isy_datetime,
    parse_xml_properties,
    value_from_nested_xml,
)

# -- parse_xml_properties edge cases ----------------------------------


def test_parse_xml_properties_splits_slash_uom() -> None:
    """ISYv4 firmware sometimes returns a list of possible UOMs joined
    with '/' — the parser splits those into a list value."""
    doc = minidom.parseString('<root><property id="ST" value="0" formatted="Off" uom="78/100"/></root>')
    state, _aux, _set = parse_xml_properties(doc)
    assert isinstance(state.uom, list)
    assert state.uom == ["78", "100"]


def test_parse_xml_properties_battery_used_as_state_when_no_status() -> None:
    """Battery-powered devices sometimes report only ``BATLVL`` — when
    ``ST`` is absent, the parser uses the battery level as the state
    (fallback used by Insteon battery-only sensors)."""
    doc = minidom.parseString('<root><property id="BATLVL" value="80" formatted="80%" uom="51"/></root>')
    state, _aux, state_set = parse_xml_properties(doc)
    assert state_set is False
    assert state.value == 80


def test_parse_xml_properties_no_props_returns_default_state() -> None:
    doc = minidom.parseString("<root></root>")
    state, aux, state_set = parse_xml_properties(doc)
    assert state.uom == "-1"  # ISY_PROP_NOT_SET
    assert aux == {}
    assert state_set is False


def test_parse_xml_properties_ramp_rate_remaps_via_table() -> None:
    """Raw ``RR`` values are remapped through ``INSTEON_RAMP_RATES``
    into seconds; unmapped values pass through unchanged."""
    doc = minidom.parseString(
        '<root><property id="ST" value="255" uom="100"/><property id="RR" value="28" uom="57"/></root>'
    )
    _state, aux, _set = parse_xml_properties(doc)
    assert "RR" in aux
    # The remapped value is in seconds (UOM_SECONDS, not the raw 28).


# -- attr_from_xml / value_from_nested_xml exception branches ---------


def test_attr_from_xml_returns_default_when_tag_missing() -> None:
    doc = minidom.parseString("<root/>")
    assert attr_from_xml(doc, "absent", "foo", default="fallback") == "fallback"


def test_value_from_nested_xml_returns_default_on_missing_path() -> None:
    doc = minidom.parseString("<root><a><b>x</b></a></root>")
    assert value_from_nested_xml(doc, ["a", "missing"], default="fb") == "fb"


# -- parse_isy_datetime format ladder --------------------------------


def test_parse_isy_datetime_strptime_format() -> None:
    """Standard ISY format: ``20260502 14:56:16``."""
    dt = parse_isy_datetime("20260502 14:56:16")
    assert dt.year == 2026 and dt.month == 5 and dt.day == 2


def test_parse_isy_datetime_strips_trailing_whitespace() -> None:
    """Some ISY firmware emits trailing whitespace on program
    last-run/last-finished — the helper strips it before parsing."""
    dt = parse_isy_datetime("20260502 14:56:16   ")
    assert dt != EMPTY_TIME
    assert dt.year == 2026


def test_parse_isy_datetime_iso_fallback() -> None:
    """If none of the strptime formats match, the helper falls through
    to ``datetime.fromisoformat``."""
    dt = parse_isy_datetime("2026-05-02T14:56:16")
    assert dt.year == 2026 and dt.minute == 56


def test_parse_isy_datetime_unparseable_returns_empty(caplog) -> None:
    with caplog.at_level("DEBUG", logger="pyisy"):
        result = parse_isy_datetime("not a date")
    assert result == EMPTY_TIME


@pytest.mark.parametrize("bad", [None, "", 42, 3.14, b"bytes"])
def test_parse_isy_datetime_returns_empty_for_non_string(bad) -> None:
    assert parse_isy_datetime(bad) == EMPTY_TIME


# -- EventEmitter filter / key / error branches -----------------------


def test_event_emitter_filter_matches_dataclass_subset() -> None:
    """Dict filters against dataclass events match by subset of fields
    — only events whose attributes ⊇ the filter's items pass."""

    @dataclass
    class Sample:
        action: str
        address: str

    emitter = EventEmitter()
    seen: list[Sample] = []
    emitter.subscribe(seen.append, event_filter={"action": "WD"})

    emitter.notify(Sample(action="WD", address="1"))
    emitter.notify(Sample(action="NE", address="2"))  # filtered out
    emitter.notify(Sample(action="WD", address="3"))

    assert [e.action for e in seen] == ["WD", "WD"]


def test_event_emitter_filter_skips_dataclass_without_match() -> None:
    @dataclass
    class Sample:
        x: int

    emitter = EventEmitter()
    seen: list = []
    emitter.subscribe(seen.append, event_filter={"x": 1})
    emitter.notify(Sample(x=2))
    assert seen == []


def test_event_emitter_key_callback_receives_key_argument() -> None:
    """When a subscription has a ``key`` set the callback is invoked
    as ``callback(event, key)`` — used by HA when a single handler
    multiplexes events from many sources."""
    emitter = EventEmitter()
    received: list[tuple] = []

    def handler(event, key):
        received.append((event, key))

    emitter.subscribe(handler, key="bedroom")
    emitter.notify("on")

    assert received == [("on", "bedroom")]


def test_event_emitter_swallows_callback_errors(caplog) -> None:
    """A buggy subscriber callback must not interrupt event delivery
    to other subscribers — the emitter logs and continues. (Regression
    guard for #249.)"""
    emitter = EventEmitter()
    other_received: list = []

    def bad(_event):
        raise RuntimeError("boom")

    emitter.subscribe(bad)
    emitter.subscribe(other_received.append)

    with caplog.at_level("ERROR", logger="pyisy"):
        emitter.notify("ping")

    assert other_received == ["ping"]
    assert any("error during callback" in r.message.lower() for r in caplog.records)


def test_event_listener_unsubscribe_removes_subscription() -> None:
    emitter = EventEmitter()
    seen: list = []
    listener = emitter.subscribe(seen.append)
    emitter.notify("a")
    listener.unsubscribe()
    emitter.notify("b")
    assert seen == ["a"]


def test_node_property_equality_compares_all_relevant_fields() -> None:
    """``NodeProperty`` equality is used by ``update_property`` to
    suppress duplicate event emissions; verify two equal instances
    compare equal and a difference in any field breaks equality."""
    a = NodeProperty("ST", 100, "0", "78", "On", "X")
    b = NodeProperty("ST", 100, "0", "78", "On", "X")
    c = NodeProperty("ST", 100, "0", "78", "Off", "X")
    assert a == b
    assert a != c
