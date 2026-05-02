"""Tests for :mod:`pyisy.clock`."""

from __future__ import annotations

from unittest.mock import MagicMock

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


def test_parse_invalid_xml_raises() -> None:
    with pytest.raises(ISYResponseParseError):
        Clock(MagicMock(), xml="not-xml")
