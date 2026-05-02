"""Tests for the per-node action methods called by the Home Assistant
``isy994`` integration.

Each action is a thin wrapper around ``isy.conn.request``; we replace that
request method with an ``AsyncMock`` after ``ISY.initialize()`` and assert
both the URL it was called with and the boolean return contract.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from pyisy.constants import (
    PROTO_GROUP,
    PROTO_INSTEON,
    TAG_GROUP,
    TAG_NODE,
)
from pyisy.isy import ISY


@pytest.fixture
def first_node(isy: ISY):
    """Pick a real Insteon node from the eisy fixture."""
    for addr, ntype in zip(isy.nodes.addresses, isy.nodes.ntypes, strict=False):
        if ntype == TAG_NODE:
            return isy.nodes[addr]
    pytest.fail("no node entries found in fixture")


@pytest.fixture
def first_group(isy: ISY):
    for addr, ntype in zip(isy.nodes.addresses, isy.nodes.ntypes, strict=False):
        if ntype == TAG_GROUP:
            return isy.nodes[addr]
    pytest.fail("no group entries found in fixture")


@pytest.fixture
def request_mock(isy: ISY) -> AsyncMock:
    """Replace the connection's request method with an ``AsyncMock`` that
    returns truthy by default (so the action methods see "success")."""
    mock = AsyncMock(return_value="<x/>")
    isy.conn.request = mock  # type: ignore[assignment]
    return mock


def _called_url(mock: AsyncMock) -> str:
    return mock.await_args.args[0]


# -- Light/dimmer commands -----------------------------------------------


@pytest.mark.parametrize(
    ("method", "expected_cmd"),
    [
        ("turn_off", "DOF"),
        ("fast_off", "DFOF"),
        ("fast_on", "DFON"),
        ("beep", "BEEP"),
        ("brighten", "BRT"),
        ("dim", "DIM"),
        ("fade_up", "FDUP"),
        ("fade_down", "FDDOWN"),
        ("fade_stop", "FDSTOP"),
    ],
)
async def test_simple_node_commands_hit_expected_url(
    first_node, request_mock: AsyncMock, method: str, expected_cmd: str
) -> None:
    result = await getattr(first_node, method)()
    assert result is True
    url = _called_url(request_mock)
    assert f"/nodes/{first_node.address.replace(' ', '%20')}/cmd/{expected_cmd}" in url


async def test_turn_on_without_value_uses_DON(first_node, request_mock: AsyncMock) -> None:
    assert await first_node.turn_on() is True
    url = _called_url(request_mock)
    assert "/cmd/DON" in url
    # No brightness value appended.
    assert not url.rstrip("/").endswith("/DON/")


async def test_turn_on_with_value_appends_brightness(first_node, request_mock: AsyncMock) -> None:
    assert await first_node.turn_on(val=128) is True
    url = _called_url(request_mock)
    assert "/cmd/DON/128" in url


async def test_turn_on_with_zero_value_falls_back_to_DOF(first_node, request_mock: AsyncMock) -> None:
    assert await first_node.turn_on(val=0) is True
    url = _called_url(request_mock)
    assert "/cmd/DOF" in url


async def test_turn_on_with_value_above_255_drops_value(first_node, request_mock: AsyncMock) -> None:
    """Values out of range fall through to a bare ``DON`` rather than
    issuing an invalid command (defensive behavior)."""
    assert await first_node.turn_on(val=999) is True
    url = _called_url(request_mock)
    assert url.endswith("/cmd/DON")


async def test_turn_on_on_group_uses_DON_even_with_zero(first_group, request_mock: AsyncMock) -> None:
    """For a ``Group`` (scene), ``turn_on`` always issues ``DON`` regardless
    of value — even ``val=0`` does not collapse to ``DOF`` the way it does
    for a Node (see the ``Group``-specific branch in ``turn_on``)."""
    assert await first_group.turn_on(val=0) is True
    assert "/cmd/DON" in _called_url(request_mock)


# -- enable / disable / rename use a different URL shape ----------------


async def test_enable_hits_change_url(first_node, request_mock: AsyncMock) -> None:
    assert await first_node.enable() is True
    assert "/nodes/" in _called_url(request_mock)
    assert "/enable" in _called_url(request_mock)


async def test_disable_hits_change_url(first_node, request_mock: AsyncMock) -> None:
    assert await first_node.disable() is True
    assert "/disable" in _called_url(request_mock)


async def test_rename_encodes_new_name_in_query(first_node, request_mock: AsyncMock) -> None:
    assert await first_node.rename("New Name") is True
    url = _called_url(request_mock)
    assert "/change?" in url
    assert "name=New" in url and "Name" in url


# -- Failure path: a falsy response from request → False return ----------


async def test_command_returns_false_on_request_failure(first_node, request_mock: AsyncMock) -> None:
    request_mock.return_value = None
    assert await first_node.turn_on() is False


async def test_disable_returns_false_on_request_failure(first_node, request_mock: AsyncMock) -> None:
    request_mock.return_value = None
    assert await first_node.disable() is False


# -- Node.query routes through ISY.query ---------------------------------


async def test_node_query_routes_through_isy_query(first_node, request_mock: AsyncMock) -> None:
    assert await first_node.query() is True
    url = _called_url(request_mock)
    # ISY.query → /rest/query/<address>
    assert "/query/" in url
    assert first_node.address.replace(" ", "%20") in url


# -- Group has the same surface; HA uses turn_on / turn_off on scenes ----


async def test_group_protocol_is_group(first_group) -> None:
    assert first_group.protocol == PROTO_GROUP


async def test_node_protocol_is_insteon(first_node) -> None:
    # Real eisy fixture has Insteon nodes; this guards against a regression
    # where node_server detection mis-classifies them.
    assert first_node.protocol == PROTO_INSTEON


# -- Node.update() polls /rest/nodes/<id>/get/ST when auto_update is off -


async def test_node_update_fetches_status_property(first_node, request_mock: AsyncMock) -> None:
    request_mock.return_value = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<nodes><node id="{first_node.address}">'
        '<property id="ST" value="0" formatted="Off" uom="100"/>'
        "</node></nodes>"
    )
    await first_node.update()
    url = _called_url(request_mock)
    assert "/nodes/" in url and "/get/ST" in url
