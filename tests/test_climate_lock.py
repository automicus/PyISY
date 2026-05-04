"""Tests for thermostat and Z-Wave lock action methods (called by HA's
climate / lock platforms in ``homeassistant.components.isy994``).

Backed by trimmed copies of real device XML extracted from the stash
exports (an Insteon 2441ZTH thermostat and a Z-Wave door lock with
``cat=111``)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from pyisy.constants import (
    PROP_SETPOINT_COOL,
    PROP_SETPOINT_HEAT,
    PROTO_INSTEON,
    PROTO_ZWAVE,
)
from pyisy.isy import ISY

# -- Thermostat ---------------------------------------------------------


@pytest.fixture
async def thermo_isy(build_isy, fixture_loader) -> ISY:
    return await build_isy(
        fixture_loader("nodes_thermostat.xml"),
        fixture_loader("status_thermostat.xml"),
    )


@pytest.fixture
def thermo_node(thermo_isy: ISY):
    return thermo_isy.nodes["91 DD DB 1"]


@pytest.fixture
def thermo_request(thermo_isy: ISY) -> AsyncMock:
    mock = AsyncMock(return_value="<x/>")
    thermo_isy.conn.request = mock  # type: ignore[assignment]
    return mock


def _called_url(mock: AsyncMock) -> str:
    return mock.await_args.args[0]


def test_thermostat_is_detected(thermo_node) -> None:
    assert thermo_node.protocol == PROTO_INSTEON
    assert thermo_node.is_thermostat is True
    assert thermo_node.is_lock is False


@pytest.mark.parametrize(
    ("mode_cmd", "expected_value"),
    [
        ("heat", "1"),
        ("cool", "2"),
        ("auto", "3"),
        ("off", "0"),
    ],
)
async def test_set_climate_mode_resolves_command_value(
    thermo_node,
    thermo_request: AsyncMock,
    mode_cmd: str,
    expected_value: str,
) -> None:
    """``set_climate_mode`` looks up the numeric value via UOM 98 and posts
    it as ``CLIMD/<value>`` — that's what HA's climate platform does."""
    assert await thermo_node.set_climate_mode(mode_cmd) is True
    url = _called_url(thermo_request)
    assert f"/cmd/CLIMD/{expected_value}" in url


async def test_set_climate_mode_returns_false_on_unknown_command(
    thermo_node, thermo_request: AsyncMock
) -> None:
    """Unknown mode strings → no request issued, ``False`` returned."""
    assert await thermo_node.set_climate_mode("not-a-mode") is False
    thermo_request.assert_not_called()


async def test_set_climate_setpoint_heat_doubles_for_uom_101(thermo_node, thermo_request: AsyncMock) -> None:
    """Insteon thermostats use UOM 101 (half-degree precision); the setpoint
    has to be doubled before being sent or temperature precision is lost."""
    assert await thermo_node.set_climate_setpoint_heat(70) is True
    url = _called_url(thermo_request)
    assert f"/cmd/{PROP_SETPOINT_HEAT}/140" in url


async def test_set_climate_setpoint_cool_doubles_for_uom_101(thermo_node, thermo_request: AsyncMock) -> None:
    assert await thermo_node.set_climate_setpoint_cool(75) is True
    url = _called_url(thermo_request)
    assert f"/cmd/{PROP_SETPOINT_COOL}/150" in url


async def test_set_climate_setpoint_issues_both_heat_and_cool(thermo_node, thermo_request: AsyncMock) -> None:
    """``set_climate_setpoint`` is the single-target API — it splits ±gap/2
    around the requested value into heat + cool calls."""
    assert await thermo_node.set_climate_setpoint(72) is True
    urls = [c.args[0] for c in thermo_request.await_args_list]
    assert any(PROP_SETPOINT_HEAT in u for u in urls)
    assert any(PROP_SETPOINT_COOL in u for u in urls)
    assert thermo_request.await_count == 2


async def test_set_fan_mode_uses_CLIFS_command(thermo_node, thermo_request: AsyncMock) -> None:
    assert await thermo_node.set_fan_mode("on") is True
    url = _called_url(thermo_request)
    assert "/cmd/CLIFS/" in url


async def test_climate_methods_short_circuit_on_non_thermostat(isy: ISY) -> None:
    """Calling thermostat methods on a plain switch returns ``None`` and
    does NOT issue a request — defensive guard from #154."""
    request_mock = AsyncMock(return_value="<x/>")
    isy.conn.request = request_mock  # type: ignore[assignment]
    # Pick a node guaranteed not to be a thermostat.
    plain = next(
        n
        for n in (
            isy.nodes[a]
            for a in isy.nodes.addresses
            if isy.nodes.ntypes[isy.nodes._address_index[a]] == "node"
        )
        if not n.is_thermostat
    )
    assert await plain.set_climate_setpoint_heat(70) is None
    assert await plain.set_climate_setpoint_cool(75) is None
    assert await plain.set_climate_setpoint(72) is None
    request_mock.assert_not_called()


# -- Z-Wave Lock --------------------------------------------------------


@pytest.fixture
async def lock_isy(build_isy, fixture_loader) -> ISY:
    return await build_isy(
        fixture_loader("nodes_zwave_lock.xml"),
        fixture_loader("status_zwave_lock.xml"),
    )


@pytest.fixture
def lock_node(lock_isy: ISY):
    return lock_isy.nodes["ZY007_1"]


@pytest.fixture
def lock_request(lock_isy: ISY) -> AsyncMock:
    mock = AsyncMock(return_value="<x/>")
    lock_isy.conn.request = mock  # type: ignore[assignment]
    return mock


def test_lock_is_detected(lock_node) -> None:
    assert lock_node.protocol == PROTO_ZWAVE
    assert lock_node.is_lock is True
    assert lock_node.is_thermostat is False
    # cat=111 came through ZWaveProperties.from_xml.
    assert lock_node.zwave_props.category == "111"


async def test_secure_lock_sends_SECMD_with_value_1(lock_node, lock_request: AsyncMock) -> None:
    assert await lock_node.secure_lock() is True
    url = _called_url(lock_request)
    assert "/cmd/SECMD/1" in url


async def test_secure_unlock_sends_SECMD_with_value_0(lock_node, lock_request: AsyncMock) -> None:
    assert await lock_node.secure_unlock() is True
    url = _called_url(lock_request)
    assert "/cmd/SECMD/0" in url


async def test_secure_lock_short_circuits_on_non_lock(isy: ISY) -> None:
    """Calling secure_lock on a non-lock returns ``None`` and issues no
    request — protects against the wrong device receiving a SECMD."""
    request_mock = AsyncMock(return_value="<x/>")
    isy.conn.request = request_mock  # type: ignore[assignment]
    plain = next(
        n
        for n in (
            isy.nodes[a]
            for a in isy.nodes.addresses
            if isy.nodes.ntypes[isy.nodes._address_index[a]] == "node"
        )
        if not n.is_lock
    )
    assert await plain.secure_lock() is None
    assert await plain.secure_unlock() is None
    request_mock.assert_not_called()


async def test_set_zwave_lock_code_uses_security_user_path(lock_node, lock_request: AsyncMock) -> None:
    assert await lock_node.set_zwave_lock_code(user_num=2, code=1234) is True
    url = _called_url(lock_request)
    # zmatter family (12) → /rest/zmatter/zwave/...
    assert "/zwave/node/ZY007_1/security/user/2/set/code/1234" in url


async def test_delete_zwave_lock_code_uses_security_user_path(lock_node, lock_request: AsyncMock) -> None:
    assert await lock_node.delete_zwave_lock_code(user_num=3) is True
    url = _called_url(lock_request)
    assert "/zwave/node/ZY007_1/security/user/3/delete" in url


async def test_zwave_lock_code_methods_reject_non_zwave(isy: ISY) -> None:
    """Setting/deleting lock codes on an Insteon node raises ``TypeError``
    rather than producing an invalid REST call."""
    plain = next(
        n
        for n in (
            isy.nodes[a]
            for a in isy.nodes.addresses
            if isy.nodes.ntypes[isy.nodes._address_index[a]] == "node"
        )
        if n.protocol == PROTO_INSTEON
    )
    with pytest.raises(TypeError):
        await plain.set_zwave_lock_code(1, 1234)
    with pytest.raises(TypeError):
        await plain.delete_zwave_lock_code(1)


# -- Z-Wave parameter set/get on a Z-Wave node --------------------------


async def test_get_zwave_parameter_parses_response(lock_node, lock_request: AsyncMock) -> None:
    lock_request.return_value = '<config paramNum="2" size="1" value="80"/>'
    result = await lock_node.get_zwave_parameter(2)
    assert result == {"parameter": 2, "size": 1, "value": "80"}
    url = _called_url(lock_request)
    assert "/zwave/node/ZY007_1/config/query/2" in url


async def test_set_zwave_parameter_validates_size(lock_node, lock_request: AsyncMock) -> None:
    """Sizes other than 1, 2, 4 are rejected before any request is made."""
    assert await lock_node.set_zwave_parameter(parameter=2, value=80, size=3) is False
    lock_request.assert_not_called()


async def test_set_zwave_parameter_rejects_non_integer_value(lock_node, lock_request: AsyncMock) -> None:
    assert await lock_node.set_zwave_parameter(parameter=2, value="abc", size=1) is False
    lock_request.assert_not_called()


async def test_set_zwave_parameter_accepts_hex_value(lock_node, lock_request: AsyncMock) -> None:
    assert await lock_node.set_zwave_parameter(parameter=2, value="0x10", size=1) is True
    url = _called_url(lock_request)
    assert "/zwave/node/ZY007_1/config/set/2/0x10/1" in url


async def test_get_zwave_parameter_rejects_non_zwave(isy: ISY) -> None:
    plain = next(
        n
        for n in (
            isy.nodes[a]
            for a in isy.nodes.addresses
            if isy.nodes.ntypes[isy.nodes._address_index[a]] == "node"
        )
        if n.protocol == PROTO_INSTEON
    )
    assert await plain.get_zwave_parameter(2) is None
    assert await plain.set_zwave_parameter(parameter=2, value=1, size=1) is False


async def test_get_zwave_parameter_rejects_non_integer(lock_node, lock_request: AsyncMock) -> None:
    """Z-Wave node, but the parameter number is non-int → returns None
    without issuing a request."""
    assert await lock_node.get_zwave_parameter("abc") is None
    lock_request.assert_not_called()


async def test_get_zwave_parameter_returns_false_on_empty_response(
    lock_node, lock_request: AsyncMock
) -> None:
    """An empty body from the controller means "couldn't read"; the
    method warns and returns False (distinct from the typed None which
    means "not a Z-Wave device")."""
    lock_request.return_value = ""
    assert await lock_node.get_zwave_parameter(2) is False


async def test_get_zwave_parameter_raises_on_malformed_xml(lock_node, lock_request: AsyncMock) -> None:
    from pyisy.exceptions import ISYResponseParseError

    lock_request.return_value = "<<not xml>>"
    with pytest.raises(ISYResponseParseError):
        await lock_node.get_zwave_parameter(2)


async def test_set_zwave_parameter_rejects_non_integer_parameter_on_zwave_node(
    lock_node, lock_request: AsyncMock
) -> None:
    """Hits the int(parameter) ValueError branch on an actual Z-Wave
    node (the protocol guard would otherwise short-circuit)."""
    assert await lock_node.set_zwave_parameter(parameter="abc", value=1, size=1) is False
    lock_request.assert_not_called()


async def test_set_zwave_parameter_rejects_invalid_hex_value(lock_node, lock_request: AsyncMock) -> None:
    """``0x...`` values must parse as base-16; ``0xZZ`` does not and
    must short-circuit before any request."""
    assert await lock_node.set_zwave_parameter(parameter=2, value="0xZZ", size=1) is False
    lock_request.assert_not_called()


async def test_set_zwave_parameter_returns_false_on_request_failure(
    lock_node, lock_request: AsyncMock
) -> None:
    lock_request.return_value = None
    assert await lock_node.set_zwave_parameter(parameter=2, value=80, size=1) is False


async def test_set_zwave_lock_code_returns_false_on_request_failure(
    lock_node, lock_request: AsyncMock
) -> None:
    lock_request.return_value = None
    assert await lock_node.set_zwave_lock_code(user_num=2, code=1234) is False


async def test_delete_zwave_lock_code_returns_false_on_request_failure(
    lock_node, lock_request: AsyncMock
) -> None:
    lock_request.return_value = None
    assert await lock_node.delete_zwave_lock_code(user_num=3) is False
