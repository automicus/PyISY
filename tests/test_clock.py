"""Tests for :mod:`pyisy.clock`."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from pyisy.clock import Clock
from pyisy.exceptions import ISYResponseParseError


def test_parse_real_time_xml(time_xml: str) -> None:
    clock = Clock(MagicMock(), xml=time_xml)

    # tz_offset is in hours; the fixture encodes -28800s = -8h.
    assert clock.tz_offset == pytest.approx(-8.0)
    assert clock.dst is True
    assert clock.military is False
    assert clock.latitude == pytest.approx(0.0)
    assert clock.longitude == pytest.approx(0.0)


def test_datetime_properties_populated(time_xml: str) -> None:
    """``last_called`` / ``sunrise`` / ``sunset`` are derived from NTP
    seconds in the fixture and exposed as ``datetime`` objects — these
    are what HA's sun-related automations read."""
    clock = Clock(MagicMock(), xml=time_xml)

    assert isinstance(clock.last_called, datetime)
    assert isinstance(clock.sunrise, datetime)
    assert isinstance(clock.sunset, datetime)
    # Fixture orders sunrise (3922976400) < last_called (3923010000) < sunset (3923022000).
    assert clock.sunrise < clock.last_called < clock.sunset


def test_parse_invalid_xml_raises() -> None:
    with pytest.raises(ISYResponseParseError):
        Clock(MagicMock(), xml="not-xml")


def test_str_includes_last_called(time_xml: str) -> None:
    clock = Clock(MagicMock(), xml=time_xml)
    s = str(clock)
    assert s.startswith("ISY Clock")
    assert str(clock.last_called) in s


def test_repr_includes_all_properties(time_xml: str) -> None:
    """``__repr__`` introspects every ``property`` on the class — useful
    for debugging, so make sure it actually walks them all without
    raising on any property accessor."""
    clock = Clock(MagicMock(), xml=time_xml)
    r = repr(clock)
    assert "ISY Clock:" in r
    # Spot-check a few properties show up in the dump.
    for name in ("tz_offset", "dst", "latitude", "longitude", "sunrise", "sunset", "military"):
        assert name in r


async def test_update_fetches_time_and_parses(time_xml: str) -> None:
    """``Clock.update()`` fetches fresh XML via ``conn.get_time`` and
    re-parses — verify both halves: the request happened, and the
    parsed values now reflect the new payload."""
    isy = MagicMock()
    isy.conn = MagicMock()
    # Start the clock with the original fixture; refresh with a payload
    # that flips DST and changes the tz to UTC.
    refreshed_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<DT><NTP>3923010000</NTP><TMZOffset>0</TMZOffset><DST>false</DST>"
        "<Lat>0.0</Lat><Long>0.0</Long><Sunrise>3922976400</Sunrise>"
        "<Sunset>3923022000</Sunset><IsMilitary>true</IsMilitary></DT>"
    )
    isy.conn.get_time = AsyncMock(return_value=refreshed_xml)

    clock = Clock(isy, xml=time_xml)
    assert clock.tz_offset == pytest.approx(-8.0)
    assert clock.dst is True
    assert clock.military is False

    await clock.update()
    isy.conn.get_time.assert_awaited_once()
    assert clock.tz_offset == pytest.approx(0.0)
    assert clock.dst is False
    assert clock.military is True


async def test_update_thread_loops_while_auto_update(time_xml: str) -> None:
    """``update_thread`` keeps polling ``Clock.update`` while
    ``isy.auto_update`` is True. Drive ``auto_update`` to flip True →
    False so the loop exits after exactly one iteration."""
    isy = MagicMock()
    auto_update_returns = iter([True, False])
    type(isy).auto_update = property(lambda _self: next(auto_update_returns))
    isy.conn = MagicMock()
    isy.conn.get_time = AsyncMock(return_value=time_xml)

    clock = Clock(isy, xml=time_xml)
    await clock.update_thread(interval=0)

    isy.conn.get_time.assert_awaited_once()
