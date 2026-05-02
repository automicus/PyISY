"""Tests for the rest of :mod:`pyisy.networking` — the manager
navigation paths, the threaded poll loop, and the ``NetworkCommand``
properties + ``run()`` happy / failure paths.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from pyisy.constants import PROTO_NETWORK
from pyisy.exceptions import ISYResponseParseError
from pyisy.networking import NetworkCommand, NetworkResources

SAMPLE_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    "<NetConfig>"
    "<NetRule><id>1</id><name>Reboot Router</name><host>192.0.2.1</host></NetRule>"
    "<NetRule><id>2</id><name>Notify</name><host>192.0.2.2</host></NetRule>"
    "</NetConfig>"
)


@pytest.fixture
def nr() -> NetworkResources:
    isy = MagicMock()
    isy.conn = MagicMock()
    return NetworkResources(isy, xml=SAMPLE_XML)


# -- parse failure ----------------------------------------------------


def test_parse_invalid_xml_raises() -> None:
    with pytest.raises(ISYResponseParseError):
        NetworkResources(MagicMock(), xml="<not really xml")


# -- __getitem__ / __setitem__ navigation -----------------------------


def test_getitem_by_int_id(nr: NetworkResources) -> None:
    assert nr[1].name == "Reboot Router"


def test_getitem_by_string_id_falls_through_to_name(nr: NetworkResources) -> None:
    """``__getitem__`` first tries ``int(val)`` → ``get_by_id``; on
    ValueError it falls through to ``get_by_name``."""
    assert nr["Notify"].address == "2"


def test_getitem_unknown_returns_none(nr: NetworkResources) -> None:
    """Both id-style and name-style lookups falling through return
    ``None`` rather than raising — distinct from ``Variables`` /
    ``Programs.__getitem__`` paths which raise or return None
    inconsistently."""
    assert nr["does-not-exist"] is None
    assert nr[999] is None


def test_setitem_silently_no_op(nr: NetworkResources) -> None:
    nr[1] = "ignored"
    # Original entry untouched.
    assert nr[1].name == "Reboot Router"


# -- get_by_* lookups --------------------------------------------------


def test_get_by_id_returns_command_or_none(nr: NetworkResources) -> None:
    assert nr.get_by_id(2) is not None
    assert nr.get_by_id(99) is None


def test_get_by_name_returns_command_or_none(nr: NetworkResources) -> None:
    assert nr.get_by_name("Reboot Router").address == "1"
    assert nr.get_by_name("Nonexistent") is None


def test_get_by_index_returns_object(nr: NetworkResources) -> None:
    cmd = nr.get_by_index(0)
    assert isinstance(cmd, NetworkCommand)


# -- threaded poll loop ----------------------------------------------


async def test_update_threaded_loops_while_auto_update(nr: NetworkResources) -> None:
    """``update_threaded`` polls ``update`` while ``isy.auto_update``
    stays True — drive a flip True → False so the loop exits cleanly
    after exactly one iteration. Same pattern as ``Clock.update_thread``."""
    auto_update_returns = iter([True, False])
    type(nr.isy).auto_update = property(lambda _self: next(auto_update_returns))
    nr.isy.conn.get_network = AsyncMock(return_value=SAMPLE_XML)

    await nr.update_threaded(interval=0)

    nr.isy.conn.get_network.assert_awaited_once()


# -- NetworkCommand properties + run() -------------------------------


def test_network_command_properties(nr: NetworkResources) -> None:
    cmd = nr.get_by_id(1)
    assert cmd.address == "1"
    assert cmd.name == "Reboot Router"
    assert cmd.protocol == PROTO_NETWORK


async def test_network_command_run_success(nr: NetworkResources) -> None:
    cmd = nr.get_by_id(1)
    nr.isy.conn.compile_url = MagicMock(return_value="http://fake/network/resources/1")
    nr.isy.conn.request = AsyncMock(return_value="<x/>")
    await cmd.run()
    nr.isy.conn.request.assert_awaited_once()


async def test_network_command_run_logs_warning_on_failure(nr: NetworkResources, caplog) -> None:
    cmd = nr.get_by_id(2)
    nr.isy.conn.compile_url = MagicMock(return_value="http://fake/network/resources/2")
    nr.isy.conn.request = AsyncMock(return_value=None)
    with caplog.at_level("WARNING", logger="pyisy"):
        await cmd.run()
    assert any("could not run networking" in r.message.lower() for r in caplog.records)
