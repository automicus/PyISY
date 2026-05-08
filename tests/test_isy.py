"""End-to-end tests for ``ISY.initialize`` driven by ``FakeConnection``."""

from __future__ import annotations

import pytest

from pyisy.exceptions import ISYResponseParseError
from pyisy.isy import ISY

from .conftest import FakeConnection


async def test_initialize_populates_managers(isy: ISY) -> None:
    assert isy.connected is True
    assert isy.configuration is not None
    assert isy.clock is not None
    assert isy.nodes is not None and isy.nodes.addresses
    assert isy.programs is not None and isy.programs.addresses
    assert isy.variables is not None
    assert isy.uuid == isy.configuration["uuid"]


async def test_initialize_increases_connections_for_iox(
    fake_connection: FakeConnection,
) -> None:
    isy = ISY(address="127.0.0.1", port=80, username="u", password="p")
    await isy.conn.close()
    isy.conn = fake_connection  # type: ignore[assignment]

    await isy.initialize()
    try:
        # The fixture config advertises model=IoX, so the connection limit
        # should have been raised.
        fake_connection.increase_available_connections.assert_called_once()
    finally:
        await isy.shutdown()


@pytest.mark.parametrize(
    "missing_method",
    ["get_status", "get_time", "get_nodes", "get_programs"],
)
async def test_initialize_raises_when_required_slot_missing(
    fake_connection: FakeConnection, missing_method: str
) -> None:
    """If the controller returns ``None`` for any of status/time/nodes/programs
    the loader must raise ``ISYResponseParseError`` (see #297). Variable defs
    and values are intentionally NOT in this list — those are allowed to be
    absent on controllers without variables configured."""

    async def _none() -> None:
        return None

    setattr(fake_connection, missing_method, _none)

    isy = ISY(address="127.0.0.1", port=80, username="u", password="p")
    await isy.conn.close()
    isy.conn = fake_connection  # type: ignore[assignment]

    with pytest.raises(ISYResponseParseError):
        await isy.initialize()
    await isy.shutdown()


async def test_initialize_tolerates_missing_variables(
    fake_connection: FakeConnection,
) -> None:
    """Missing variable defs/values are non-fatal — controllers without
    variables configured should still load."""

    async def _empty_defs() -> list[str]:
        return ["/CONF/INTEGER.VAR not found", "/CONF/STATE.VAR not found"]

    async def _none() -> None:
        return None

    fake_connection.get_variable_defs = _empty_defs  # type: ignore[assignment]
    fake_connection.get_variables = _none  # type: ignore[assignment]

    isy = ISY(address="127.0.0.1", port=80, username="u", password="p")
    await isy.conn.close()
    isy.conn = fake_connection  # type: ignore[assignment]

    await isy.initialize()
    try:
        assert isy.connected
        assert isy.variables is not None
        assert isy.variables.vids == {1: [], 2: []}
    finally:
        await isy.shutdown()


async def test_auto_update_with_websocket_is_noop(fake_connection: FakeConnection, caplog) -> None:
    """Setting ``auto_update = True`` when websockets are enabled must not
    open a TCP event stream; the two transports are mutually exclusive."""
    isy = ISY(
        address="127.0.0.1",
        port=80,
        username="u",
        password="p",
        use_websocket=True,
    )
    await isy.conn.close()
    isy.conn = fake_connection  # type: ignore[assignment]
    await isy.initialize()
    try:
        with caplog.at_level("WARNING", logger="pyisy"):
            isy.auto_update = True
        assert isy._events is None
        assert any("websocket" in r.message.lower() for r in caplog.records)
    finally:
        if isy.websocket is not None:
            isy.websocket.stop()
        await isy.shutdown()


async def test_status_applied_to_nodes(isy: ISY, status_xml: str) -> None:
    """At least one node referenced in status.xml has a status property after
    full initialize() — the load chain explicitly applies status xml after
    constructing the Nodes manager."""
    from xml.dom import minidom

    status_doc = minidom.parseString(status_xml)
    status_ids = [n.attributes["id"].value for n in status_doc.getElementsByTagName("node")]
    matched = [a for a in status_ids if a in isy.nodes.addresses]
    assert matched, "status.xml has no overlap with parsed nodes"
    # Confirm at least one of those nodes has a status property populated.
    any_status = any(isy.nodes[a].aux_properties or isy.nodes[a].status not in (None,) for a in matched)
    assert any_status
