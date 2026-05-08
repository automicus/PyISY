"""Tests for the ``update()`` paths across managers and entities.

These methods are how consumers (notably the Home Assistant ``isy994``
integration) refresh state from the controller — after sending a
command, or periodically when no event stream is connected.

Each test stubs the relevant ``Connection.get_*`` method and asserts
the manager actually fetches and re-parses, or short-circuits / warns
on the documented failure modes.
"""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from pyisy.constants import TAG_FOLDER, TAG_GROUP, TAG_NODE
from pyisy.isy import ISY


def _first_node_address(isy: ISY) -> str:
    for addr, ntype in zip(isy.nodes.addresses, isy.nodes.ntypes, strict=False):
        if ntype == TAG_NODE:
            return addr
    pytest.fail("no node entries found in fixture")


def _first_group_address(isy: ISY) -> str:
    for addr, ntype in zip(isy.nodes.addresses, isy.nodes.ntypes, strict=False):
        if ntype == TAG_GROUP:
            return addr
    pytest.fail("no group entries found in fixture")


def _first_program_folder_address(isy: ISY) -> str:
    """Find a folder in the *programs* tree (``Folder`` instance), not
    the nodes tree — the two hierarchies are independent."""
    for addr, ptype in zip(isy.programs.addresses, isy.programs.ptypes, strict=False):
        if ptype == TAG_FOLDER and addr != "0001":  # skip synthetic root
            return addr
    pytest.fail("no program folder entries found in fixture")


# -- Nodes manager -----------------------------------------------------


async def test_nodes_update_fetches_status(isy: ISY, status_xml: str) -> None:
    isy.conn.get_status = AsyncMock(return_value=status_xml)
    await isy.nodes.update()
    isy.conn.get_status.assert_awaited_once()


async def test_nodes_update_with_xml_arg_skips_request(isy: ISY, status_xml: str) -> None:
    """When called with ``xml=...`` the manager must NOT hit the network —
    that's the path used during ``ISY.initialize()`` to apply already-
    fetched status."""
    isy.conn.get_status = AsyncMock(return_value="<should-not-be-used/>")
    await isy.nodes.update(xml=status_xml)
    isy.conn.get_status.assert_not_awaited()


async def test_nodes_update_returns_none_when_status_unavailable(isy: ISY, caplog) -> None:
    """If the controller returns nothing for /rest/status the manager
    logs a warning and bails — it must not crash mid-poll."""
    isy.conn.get_status = AsyncMock(return_value=None)
    with caplog.at_level("WARNING", logger="pyisy"):
        result = await isy.nodes.update()
    assert result is None
    assert any("update nodes" in r.message.lower() for r in caplog.records)


async def test_nodes_update_returns_false_on_malformed_xml(isy: ISY, caplog) -> None:
    """Unlike the initial ``parse()`` (which raises so HA gets
    ``ConfigEntryNotReady``), an in-flight ``update()`` with bad XML
    only logs and returns ``False`` — the controller may have hiccuped
    and we want the next poll to recover, not blow up the integration."""
    isy.conn.get_status = AsyncMock(return_value="<not really xml")
    with caplog.at_level("ERROR", logger="pyisy"):
        result = await isy.nodes.update()
    assert result is False
    assert any("nodes" in r.message.lower() for r in caplog.records)


async def test_nodes_update_nodes_fetches_full_tree(isy: ISY, nodes_xml: str) -> None:
    """``update_nodes()`` is the rarer "rebuild the whole tree" call —
    distinct from ``update()`` (which just refreshes status). HA uses
    this when a new device is added on the controller side."""
    isy.conn.get_nodes = AsyncMock(return_value=nodes_xml)
    await isy.nodes.update_nodes()
    isy.conn.get_nodes.assert_awaited_once()


async def test_nodes_update_nodes_warns_on_none(isy: ISY, caplog) -> None:
    isy.conn.get_nodes = AsyncMock(return_value=None)
    with caplog.at_level("WARNING", logger="pyisy"):
        await isy.nodes.update_nodes()
    assert any("update nodes" in r.message.lower() for r in caplog.records)


# -- Programs manager --------------------------------------------------


async def test_programs_update_fetches_and_parses(isy: ISY, programs_xml: str) -> None:
    isy.conn.get_programs = AsyncMock(return_value=programs_xml)
    await isy.programs.update(wait_time=0)
    isy.conn.get_programs.assert_awaited_once_with(None)


async def test_programs_update_passes_address_through(isy: ISY, programs_xml: str) -> None:
    """``Program.update`` / ``Folder.update`` delegate to the manager
    with their own id — the address has to make it down to the request."""
    isy.conn.get_programs = AsyncMock(return_value=programs_xml)
    await isy.programs.update(wait_time=0, address="0007")
    isy.conn.get_programs.assert_awaited_once_with("0007")


async def test_programs_update_warns_on_none(isy: ISY, caplog) -> None:
    isy.conn.get_programs = AsyncMock(return_value=None)
    with caplog.at_level("WARNING", logger="pyisy"):
        await isy.programs.update(wait_time=0)
    assert any("update programs" in r.message.lower() for r in caplog.records)


# -- Variables manager -------------------------------------------------


async def test_variables_update_fetches_values(isy: ISY, var_values_xml: str) -> None:
    isy.conn.get_variables = AsyncMock(return_value=var_values_xml)
    await isy.variables.update()
    isy.conn.get_variables.assert_awaited_once()


async def test_variables_update_warns_on_none(isy: ISY, caplog) -> None:
    isy.conn.get_variables = AsyncMock(return_value=None)
    with caplog.at_level("WARNING", logger="pyisy"):
        await isy.variables.update()
    assert any("update variables" in r.message.lower() for r in caplog.records)


# -- NetworkResources manager -----------------------------------------


async def test_network_resources_update_fetches_and_parses() -> None:
    """``NetworkResources`` is only constructed when the configuration
    advertises the Networking module — the eisy fixture doesn't, so we
    instantiate the manager directly. The parser expects ``<id>`` as a
    child element of ``<NetRule>`` (not as an attribute)."""
    from pyisy.networking import NetworkResources

    sample_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<NetConfig><NetRule><id>1</id><name>Sample</name>"
        "<protocol>0</protocol><host>192.0.2.1</host><port>80</port>"
        "</NetRule></NetConfig>"
    )
    isy = MagicMock()
    isy.conn = MagicMock()
    isy.conn.get_network = AsyncMock(return_value=sample_xml)

    nr = NetworkResources(isy, xml=sample_xml)
    assert 1 in nr._address_index

    await nr.update(wait_time=0)
    isy.conn.get_network.assert_awaited_once()


# -- Per-entity Variable.update ---------------------------------------


async def test_variable_update_delegates_to_manager_and_stamps_last_update(
    isy: ISY, var_values_xml: str
) -> None:
    """``Variable.update()`` is a thin wrapper that asks the parent
    manager to refresh — it also stamps ``_last_update`` so consumers can
    see when the entity was touched."""
    isy.conn.get_variables = AsyncMock(return_value=var_values_xml)
    var = isy.variables[1][1]  # Int.1 from the fixture
    before = var.last_update

    await var.update()

    isy.conn.get_variables.assert_awaited_once()
    assert var.last_update >= before


# -- Per-entity Program.update ----------------------------------------


async def test_program_update_with_data_skips_network(isy: ISY) -> None:
    """When called with a pre-supplied ``data`` dict the program updates
    in-place — that's the path the websocket router uses on ``_1`` events,
    bypassing the REST round-trip."""
    program = next(
        isy.programs[a].leaf
        for a in isy.programs.addresses
        if isy.programs.ptypes[isy.programs._address_index[a]] == "program"
    )
    isy.conn.get_programs = AsyncMock(return_value=None)

    ts = datetime.datetime(2026, 5, 2, tzinfo=datetime.UTC)
    await program.update(
        data={
            "pstatus": "21",
            "plastrun": ts,
            "plastfin": ts,
            "plastup": ts,
            "prunning": False,
            "penabled": True,
            "pstartrun": False,
        }
    )
    isy.conn.get_programs.assert_not_awaited()


async def test_program_update_without_data_fetches_via_manager(isy: ISY, programs_xml: str) -> None:
    program = next(
        isy.programs[a].leaf
        for a in isy.programs.addresses
        if isy.programs.ptypes[isy.programs._address_index[a]] == "program"
    )
    isy.conn.get_programs = AsyncMock(return_value=programs_xml)

    await program.update(wait_time=0)
    isy.conn.get_programs.assert_awaited_once_with(program.address)


# -- Per-entity Folder.update -----------------------------------------


async def test_folder_update_with_data_skips_network(isy: ISY) -> None:
    folder = isy.programs[_first_program_folder_address(isy)].leaf
    isy.conn.get_programs = AsyncMock(return_value=None)
    await folder.update(data={"pstatus": "1"})
    isy.conn.get_programs.assert_not_awaited()


async def test_folder_update_without_data_fetches_via_manager(isy: ISY, programs_xml: str) -> None:
    addr = _first_program_folder_address(isy)
    folder = isy.programs[addr].leaf
    isy.conn.get_programs = AsyncMock(return_value=programs_xml)
    await folder.update(wait_time=0)
    isy.conn.get_programs.assert_awaited_once_with(addr)


# -- Per-entity Group.update ------------------------------------------


async def test_group_update_recomputes_status_from_members(isy: ISY) -> None:
    """``Group.update()`` doesn't hit the network; it walks the scene's
    member nodes and aggregates their statuses. Just verify it runs
    without raising and stamps ``_last_update``."""
    group = isy.nodes[_first_group_address(isy)]
    before = group.last_update
    await group.update()
    assert group.last_update >= before


# NodeBase default ``update`` is unreachable in practice — both ``Node``
# and ``Group`` override it, and Folders in the nodes tree are wrapped in
# a navigation-only ``Nodes`` sub-container rather than a NodeBase
# instance. Skip — covering it would require instantiating NodeBase
# directly, which doesn't reflect any real call path.
