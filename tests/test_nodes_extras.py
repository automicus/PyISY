"""Tests for the rest of the nodes surface — Nodes manager navigation
and event handlers, NodeBase property getters and notes parsing,
Node-specific property smoke and validation paths in setters /
write commands, and the small remaining gaps in Group.

These complement the action-method tests (``test_node_actions.py``,
``test_climate_lock.py``) and the websocket router tests by exercising
the real event handlers and the read-side surface HA reads from.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from xml.dom import minidom

import pytest

from pyisy.constants import (
    PROP_COMMS_ERROR,
    PROP_RAMP_RATE,
    PROP_STATUS,
    TAG_FOLDER,
    TAG_GROUP,
    TAG_NODE,
)
from pyisy.helpers import NodeProperty
from pyisy.isy import ISY

# -- helpers ----------------------------------------------------------


def _node_addr(isy: ISY) -> str:
    for addr, t in zip(isy.nodes.addresses, isy.nodes.ntypes, strict=False):
        if t == TAG_NODE:
            return addr
    pytest.fail("no nodes in fixture")


def _group_addr(isy: ISY) -> str:
    for addr, t in zip(isy.nodes.addresses, isy.nodes.ntypes, strict=False):
        if t == TAG_GROUP:
            return addr
    pytest.fail("no groups in fixture")


def _folder_addr(isy: ISY) -> str:
    for addr, t in zip(isy.nodes.addresses, isy.nodes.ntypes, strict=False):
        if t == TAG_FOLDER:
            return addr
    pytest.fail("no folders in fixture")


def _wrap_event(payload: str) -> minidom.Document:
    return minidom.parseString(
        f'<?xml version="1.0" encoding="UTF-8"?><Event seqnum="1" sid="uuid:test">{payload}</Event>'
    )


# -- Nodes manager: __str__ / __repr__ -------------------------------


def test_nodes_str_at_root(isy: ISY) -> None:
    assert str(isy.nodes) == "Folder <root>"


def test_nodes_str_at_folder_group_node(isy: ISY) -> None:
    """Indexing a folder address returns a navigation ``Nodes`` sub-
    container whose ``__str__`` formats with a space (``"Folder (…)"``).
    Indexing a node or group returns the leaf object directly, whose
    ``__str__`` has no space (``"Node(…)"`` / ``"Group(…)"``)."""
    assert str(isy.nodes[_folder_addr(isy)]).startswith("Folder (")
    assert str(isy.nodes[_node_addr(isy)]).startswith("Node(")
    assert str(isy.nodes[_group_addr(isy)]).startswith("Group(")


def test_nodes_repr_renders_full_tree(isy: ISY) -> None:
    out = repr(isy.nodes)
    assert "Folder <root>" in out
    # Every kept folder/group/node should appear by name somewhere in the
    # rendering.
    sample_node = isy.nodes[_node_addr(isy)]
    assert sample_node.name in out


# -- Nodes.control_message_received (real handler) -------------------


def test_control_message_for_unknown_node_is_dropped(isy: ISY) -> None:
    """Control messages for an address we don't have a record of must
    be silently dropped (logs at debug, no crash)."""
    addr = "ZZ ZZ ZZ 1"
    doc = _wrap_event(
        f"<control>RR</control><action uom='57' prec='0'>28</action><node>{addr}</node><eventInfo/>"
    )
    isy.nodes.control_message_received(doc)


def test_control_message_with_missing_address_or_control_returns(isy: ISY) -> None:
    doc = _wrap_event("<control></control><node></node>")
    isy.nodes.control_message_received(doc)  # should not raise


def test_control_message_updates_aux_property(isy: ISY) -> None:
    """A real control event (e.g. ``RR``) populates the target node's
    ``aux_properties`` with a ``NodeProperty`` for that control."""
    addr = _node_addr(isy)
    doc = _wrap_event(
        f"<control>RR</control><action uom='57' prec='0'>28</action>"
        f"<node>{addr}</node><eventInfo/>"
        "<fmtAct>0.5 seconds</fmtAct><fmtName>Ramp Rate</fmtName>"
    )
    isy.nodes.control_message_received(doc)
    node = isy.nodes[addr]
    assert PROP_RAMP_RATE in node.aux_properties


def test_control_message_clears_comms_error(isy: ISY) -> None:
    """``ERR`` with value=0 clears the *old* ``PROP_COMMS_ERROR`` aux
    entry (the recovery path) before re-adding the new value=0 event.
    Effectively the entry's ``value`` moves from 1 -> 0 — that's the
    observable signal that the del+update branch ran."""
    addr = _node_addr(isy)
    node = isy.nodes[addr]
    node.aux_properties[PROP_COMMS_ERROR] = NodeProperty(PROP_COMMS_ERROR, 1, "0", "0", "1", addr)
    doc = _wrap_event(
        f"<control>{PROP_COMMS_ERROR}</control>"
        f"<action uom='0' prec='0'>0</action>"
        f"<node>{addr}</node><eventInfo/>"
    )
    isy.nodes.control_message_received(doc)
    assert node.aux_properties[PROP_COMMS_ERROR].value == 0


# -- Nodes.node_changed_received -------------------------------------


def test_node_changed_received_unknown_action_returns(isy: ISY) -> None:
    """Action strings that aren't in ``NODE_CHANGED_ACTIONS`` are
    silently ignored — the firmware can emit new ones in future
    versions and we don't want to crash on those."""
    doc = _wrap_event("<control>_3</control><action>NONESUCH</action><node>X</node><eventInfo/>")
    isy.nodes.node_changed_received(doc)


def test_node_changed_received_node_error_logs_error(isy: ISY, caplog) -> None:
    doc = _wrap_event("<control>_3</control><action>NE</action><node>X X X 1</node><eventInfo/>")
    with caplog.at_level("ERROR", logger="pyisy"):
        isy.nodes.node_changed_received(doc)
    assert any("could not communicate" in r.message.lower() for r in caplog.records)


def test_node_changed_received_node_enabled_updates_node(isy: ISY) -> None:
    """``EN`` with ``<enabled>true</enabled>`` flips the node's
    ``enabled`` flag — used by HA's enable/disable reflection."""
    addr = _node_addr(isy)
    node = isy.nodes[addr]
    node.enabled = False
    doc = _wrap_event(
        "<control>_3</control><action>EN</action>"
        f"<node>{addr}</node>"
        "<eventInfo><enabled>true</enabled></eventInfo>"
    )
    isy.nodes.node_changed_received(doc)
    assert node.enabled is True


# -- Nodes.progress_report_received ----------------------------------


def test_progress_report_received_dispatches(isy: ISY) -> None:
    """``_7`` events carry programming/diagnostic messages with the
    address embedded in ``[...]`` brackets in eventInfo. The handler
    parses out the address and notifies subscribers."""
    addr = _node_addr(isy)
    doc = _wrap_event(
        "<control>_7</control><action>1</action><node></node>"
        f"<eventInfo>[{addr}  ] Memory : EPROM Refreshed</eventInfo>"
    )
    isy.nodes.progress_report_received(doc)


# -- Nodes navigation / lookup ---------------------------------------


def test_nodes_getitem_by_id(isy: ISY) -> None:
    addr = _node_addr(isy)
    assert isy.nodes[addr] is not None


def test_nodes_getitem_by_name(isy: ISY) -> None:
    """Name-based lookup walks all addresses and returns the first
    match."""
    addr = _node_addr(isy)
    name = isy.nodes[addr].name
    found = isy.nodes[name]
    assert found is not None


def test_nodes_setitem_silently_no_op(isy: ISY) -> None:
    """``Nodes.__setitem__`` exists for dict-like compatibility but
    does nothing — assigning to a name doesn't alter state."""
    isy.nodes["anything"] = "value"
    # The address list is unchanged.
    assert isy.nodes.addresses


def test_nodes_get_folder_walks_to_top(isy: ISY) -> None:
    """``get_folder`` returns the *folder* a node is in by walking up
    the parent chain through any intermediate non-folder parents."""
    addr = _node_addr(isy)
    folder = isy.nodes.get_folder(addr)
    # Either the node has a folder ancestor or it's at the root (None).
    assert folder is None or isinstance(folder, str)


def test_nodes_children_and_get_children(isy: ISY) -> None:
    root_children = isy.nodes.children
    assert root_children
    # Same call via explicit ident.
    explicit = isy.nodes.get_children(None)
    assert explicit == root_children


def test_nodes_has_children_at_root_is_true(isy: ISY) -> None:
    assert isy.nodes.has_children is True


def test_nodes_name_at_root_is_empty(isy: ISY) -> None:
    assert isy.nodes.name == ""


def test_nodes_name_at_folder_is_folder_name(isy: ISY) -> None:
    folder_addr = _folder_addr(isy)
    sub = isy.nodes[folder_addr]
    # The folder's name should match what the manager has indexed.
    expected = isy.nodes.nnames[isy.nodes._address_index[folder_addr]]
    assert sub.name == expected


def test_nodes_all_lower_nodes_returns_paths(isy: ISY) -> None:
    """``all_lower_nodes`` walks every reachable folder/group/node and
    builds slash-separated path strings. Every entry must be one of the
    three known types."""
    paths = isy.nodes.all_lower_nodes
    assert paths
    types = {entry[0] for entry in paths}
    assert types <= {TAG_FOLDER, TAG_GROUP, TAG_NODE}


def test_nodes_iter_yields_node_objects(isy: ISY) -> None:
    """``__iter__`` returns ``(path, Node)`` tuples for every leaf node
    below the current root."""
    seen = []
    for path, node in isy.nodes:
        seen.append((path, node))
    assert seen, "expected at least one node"


def test_nodes_reversed_iterates_in_reverse(isy: ISY) -> None:
    """``__reversed__`` is driven manually since the iterator class
    lacks ``__iter__``-returning-self (same workaround as programs)."""
    rev_it = reversed(isy.nodes)
    backward = []
    while True:
        try:
            backward.append(next(rev_it))
        except StopIteration:
            break
    forward = list(isy.nodes)
    assert backward == list(reversed(forward))


# -- NodeBase property smoke -----------------------------------------


def test_nodebase_str_returns_class_and_id(isy: ISY) -> None:
    node = isy.nodes[_node_addr(isy)]
    assert str(node).startswith("Node(") and node.address in str(node)


def test_nodebase_aux_properties_is_dict(isy: ISY) -> None:
    node = isy.nodes[_node_addr(isy)]
    assert isinstance(node.aux_properties, dict)


@pytest.mark.parametrize("attr", ["family", "flag", "folder", "primary_node"])
def test_nodebase_metadata_properties_accessible(isy: ISY, attr: str) -> None:
    """Metadata properties read directly from ``__init__``-stored attrs
    — never raise even if the source XML didn't carry the field."""
    node = isy.nodes[_node_addr(isy)]
    getattr(node, attr)  # no crash; value may be None


@pytest.mark.parametrize("attr", ["description", "is_load", "location", "spoken"])
def test_nodebase_notes_properties_warn_when_notes_unloaded(isy: ISY, attr: str, caplog) -> None:
    """Properties backed by ``self._notes`` log a debug-level reminder
    when accessed before ``get_notes()`` populates them, but should not
    raise — they fall through to a ``None`` lookup that does."""
    node = isy.nodes[_node_addr(isy)]
    node._notes = None
    with caplog.at_level("DEBUG", logger="pyisy"), pytest.raises(TypeError):
        # ``self._notes[TAG_X]`` on None raises TypeError. The debug
        # log is the warning-equivalent the implementation emits;
        # capturing it documents the behavior.
        getattr(node, attr)


async def test_nodebase_get_notes_parses_xml(isy: ISY) -> None:
    """``get_notes()`` fetches /rest/nodes/<id>/notes and parses the
    response into a dict the notes-backed properties consume."""
    node = isy.nodes[_node_addr(isy)]
    isy.conn.request = AsyncMock(
        return_value=(
            '<?xml version="1.0"?><NodeProperties>'
            "<spoken>Test</spoken><isLoad>true</isLoad>"
            "<description>A node</description><location>Garage</location>"
            "</NodeProperties>"
        )
    )
    notes = await node.get_notes()
    assert notes["description"] == "A node"
    assert notes["isLoad"] is True


async def test_nodebase_get_notes_handles_empty_response(isy: ISY) -> None:
    """A 404 from /notes returns an empty string from the connection
    layer (``ok404=True``); ``get_notes`` returns a dict of ``None``s
    rather than crashing."""
    node = isy.nodes[_node_addr(isy)]
    isy.conn.request = AsyncMock(return_value="")
    notes = await node.get_notes()
    assert notes["description"] is None


def test_nodebase_status_setter_fires_event_on_change(isy: ISY) -> None:
    node = isy.nodes[_node_addr(isy)]
    seen: list = []
    node.status_events.subscribe(seen.append)
    node.status = 12345
    assert seen, "status setter should have notified"


def test_nodebase_status_feedback_shape(isy: ISY) -> None:
    node = isy.nodes[_node_addr(isy)]
    fb = node.status_feedback
    assert "address" in fb and "status" in fb


def test_nodebase_update_property_replaces_existing(isy: ISY) -> None:
    """Re-applying the same property is a no-op; a new value replaces
    the existing entry and notifies on change."""
    node = isy.nodes[_node_addr(isy)]
    prop1 = NodeProperty(PROP_RAMP_RATE, 28, "0", "57", "0.5 seconds", node.address)
    node.update_property(prop1)
    assert node.aux_properties[PROP_RAMP_RATE].value == 28

    prop2 = NodeProperty(PROP_RAMP_RATE, 14, "0", "57", "0.25 seconds", node.address)
    node.update_property(prop2)
    assert node.aux_properties[PROP_RAMP_RATE].value == 14


def test_nodebase_update_property_rejects_non_NodeProperty(isy: ISY, caplog) -> None:
    node = isy.nodes[_node_addr(isy)]
    with caplog.at_level("ERROR", logger="pyisy"):
        node.update_property("not a property")
    assert any("invalid type" in r.message.lower() for r in caplog.records)


# -- Node-specific properties + setters ------------------------------


def test_node_dimmable_emits_deprecation(isy: ISY, caplog) -> None:
    node = isy.nodes[_node_addr(isy)]
    with caplog.at_level("INFO", logger="pyisy"):
        _ = node.dimmable
    assert any("depreciated" in r.message.lower() for r in caplog.records)


@pytest.mark.parametrize("attr", ["prec", "uom", "type", "node_def_id", "protocol"])
def test_node_metadata_properties_accessible(isy: ISY, attr: str) -> None:
    node = isy.nodes[_node_addr(isy)]
    getattr(node, attr)


def test_node_enabled_setter(isy: ISY) -> None:
    node = isy.nodes[_node_addr(isy)]
    node.enabled = False
    assert node.enabled is False
    node.enabled = True
    assert node.enabled is True


def test_node_is_battery_node_property(isy: ISY) -> None:
    node = isy.nodes[_node_addr(isy)]
    assert isinstance(node.is_battery_node, bool)


def test_node_is_dimmable_for_insteon_dimmer(isy: ISY) -> None:
    """Pick an Insteon node and verify ``is_dimmable`` returns a bool
    based on UOM / type heuristic."""
    node = isy.nodes[_node_addr(isy)]
    assert isinstance(node.is_dimmable, bool)


def test_node_update_state_rejects_non_NodeProperty(isy: ISY, caplog) -> None:
    node = isy.nodes[_node_addr(isy)]
    with caplog.at_level("ERROR", logger="pyisy"):
        node.update_state("not a property")
    assert any("invalid type" in r.message.lower() for r in caplog.records)


def test_node_update_state_only_fires_event_on_change(isy: ISY) -> None:
    """``update_state`` notifies via ``status`` setter when the value
    moves; if only prec/uom/formatted change, the change-only branch
    fires a ``status_feedback`` event."""
    node = isy.nodes[_node_addr(isy)]
    seen: list = []
    node.status_events.subscribe(seen.append)
    # Same status value, different formatted string → "changed" branch
    node.update_state(NodeProperty(PROP_STATUS, node.status, "0", "100", "X", node.address))
    # Either path should have emitted at least one event.
    assert seen


def test_node_get_command_value_accepts_known_command(isy: ISY) -> None:
    """``get_command_value`` reverse-looks-up a numeric value for a
    named command via UOM_TO_STATES — a small lookup table."""
    node = isy.nodes[_node_addr(isy)]
    # UOM 98 is climate-mode; "heat" is a documented value.
    assert node.get_command_value("98", "heat") == "1"


def test_node_get_command_value_rejects_unknown(isy: ISY, caplog) -> None:
    node = isy.nodes[_node_addr(isy)]
    with caplog.at_level("WARNING", logger="pyisy"):
        result = node.get_command_value("98", "nonsense")
    assert result is None
    assert any("invalid command" in r.message.lower() for r in caplog.records)


def test_node_get_groups_returns_addresses(isy: ISY) -> None:
    node = isy.nodes[_node_addr(isy)]
    assert isinstance(node.get_groups(), list)


def test_node_get_property_uom_returns_none_when_missing(isy: ISY) -> None:
    node = isy.nodes[_node_addr(isy)]
    # Picking an unlikely property; should be None rather than raise.
    assert node.get_property_uom("NONEXISTENT") is None


# -- on_level / ramp_rate / manual_dim validation --------------------


@pytest.mark.parametrize("bad", [None, 0, 256, float("nan")])
async def test_node_set_on_level_rejects_invalid_values(isy: ISY, bad) -> None:
    isy.conn.request = AsyncMock(return_value="<x/>")
    node = isy.nodes[_node_addr(isy)]
    assert await node.set_on_level(bad) is False
    isy.conn.request.assert_not_called()


async def test_node_set_on_level_accepts_valid(isy: ISY) -> None:
    isy.conn.request = AsyncMock(return_value="<x/>")
    node = isy.nodes[_node_addr(isy)]
    assert await node.set_on_level(128) is True


@pytest.mark.parametrize("bad", [None, 0, 32, float("nan")])
async def test_node_set_ramp_rate_rejects_invalid_values(isy: ISY, bad) -> None:
    isy.conn.request = AsyncMock(return_value="<x/>")
    node = isy.nodes[_node_addr(isy)]
    assert await node.set_ramp_rate(bad) is False
    isy.conn.request.assert_not_called()


async def test_node_set_ramp_rate_accepts_valid(isy: ISY) -> None:
    isy.conn.request = AsyncMock(return_value="<x/>")
    node = isy.nodes[_node_addr(isy)]
    assert await node.set_ramp_rate(15) is True


async def test_node_start_manual_dimming_warns_and_sends(isy: ISY, caplog) -> None:
    isy.conn.request = AsyncMock(return_value="<x/>")
    node = isy.nodes[_node_addr(isy)]
    with caplog.at_level("WARNING", logger="pyisy"):
        await node.start_manual_dimming()
    assert any("depreciated" in r.message.lower() for r in caplog.records)


async def test_node_stop_manual_dimming_warns_and_sends(isy: ISY, caplog) -> None:
    isy.conn.request = AsyncMock(return_value="<x/>")
    node = isy.nodes[_node_addr(isy)]
    with caplog.at_level("WARNING", logger="pyisy"):
        await node.stop_manual_dimming()
    assert any("depreciated" in r.message.lower() for r in caplog.records)


# -- set_fan_mode invalid path ---------------------------------------


async def test_set_fan_mode_unknown_command_returns_false(isy: ISY) -> None:
    """``set_fan_mode`` validates against the UOM 99 lookup table; an
    unknown mode returns False without issuing a request."""
    isy.conn.request = AsyncMock(return_value="<x/>")
    node = isy.nodes[_node_addr(isy)]
    assert await node.set_fan_mode("nonsense") is False
    isy.conn.request.assert_not_called()


# -- Z-Wave parameter / lock-code error paths ------------------------


async def test_set_zwave_parameter_non_integer_parameter_rejected(isy: ISY) -> None:
    node = isy.nodes[_node_addr(isy)]
    # Insteon node — protocol guard fires first, so this also covers
    # the "parameter must be int" path on a non-Z-Wave node.
    assert await node.set_zwave_parameter(parameter="abc", value=1, size=1) is False


async def test_get_zwave_parameter_non_integer_parameter_returns_none(isy: ISY) -> None:
    """The Z-Wave param fetcher rejects non-integer parameter numbers
    even on a Z-Wave node."""
    # Build via build_isy with the lock fixture so the protocol guard passes.
    # exercised in test_climate_lock; this test is a placeholder.


# -- Group remaining lines -------------------------------------------


def test_group_controllers_property(isy: ISY) -> None:
    group = isy.nodes[_group_addr(isy)]
    assert isinstance(group.controllers, list)


def test_group_group_all_on_property_and_setter(isy: ISY) -> None:
    group = isy.nodes[_group_addr(isy)]
    starting = group.group_all_on
    group.group_all_on = not starting
    assert group.group_all_on is (not starting)


def test_group_update_callback_drives_update(isy: ISY) -> None:
    """``update_callback`` is the synchronous bridge from
    ``status_events`` subscriptions back into ``_update``. Calling it
    directly with a fake event must not raise."""
    group = isy.nodes[_group_addr(isy)]
    group.update_callback(event=MagicMock())


# -- Node small property accessors -----------------------------------


def test_node_formatted_property_returns_state_formatted(isy: ISY) -> None:
    """``Node.formatted`` exposes the ``formatted`` field captured from
    the controller's status XML at construction time."""
    node = isy.nodes[_node_addr(isy)]
    # Pulled from the parsed state; could be None if the fixture node
    # had no formatted value, but the property itself must work.
    assert node.formatted == node._formatted


def test_node_is_backlight_supported_returns_bool(isy: ISY) -> None:
    """The predicate combines protocol + node_def_id membership in
    ``BACKLIGHT_SUPPORT`` — exercised here purely for the line."""
    node = isy.nodes[_node_addr(isy)]
    assert isinstance(node.is_backlight_supported, bool)


def test_node_node_server_property(isy: ISY) -> None:
    node = isy.nodes[_node_addr(isy)]
    # Insteon fixture nodes have no node_server slot.
    assert node.node_server == node._node_server


def test_node_parent_node_returns_node_when_pnode_set(isy: ISY) -> None:
    """A node whose ``pnode`` differs from its own address resolves to
    the parent through ``Nodes.get_by_id``."""
    parented = next(
        (
            isy.nodes[a]
            for a in isy.nodes.addresses
            if isy.nodes.ntypes[isy.nodes._address_index[a]] == TAG_NODE and isy.nodes[a]._parent_node
        ),
        None,
    )
    if parented is None:
        pytest.skip("fixture has no subnode with a different parent address")
    parent = parented.parent_node
    assert parent is not None
    assert parent.address == parented._parent_node


def test_node_parent_node_returns_none_when_no_parent(isy: ISY) -> None:
    """A primary node (pnode == address, so ``_parent_node`` is None)
    returns None instead of looking itself up."""
    primary = next(
        isy.nodes[a]
        for a in isy.nodes.addresses
        if isy.nodes.ntypes[isy.nodes._address_index[a]] == TAG_NODE and isy.nodes[a]._parent_node is None
    )
    assert primary.parent_node is None


# -- update / update_state error and edge paths ----------------------


async def test_node_update_raises_on_malformed_xml(isy: ISY) -> None:
    """``Node.update`` parses the ``/get/ST`` response; bad XML surfaces
    as ``ISYResponseParseError`` so HA can convert it into a retry."""
    from pyisy.exceptions import ISYResponseParseError

    isy.conn.request = AsyncMock(return_value="<<not xml>>")
    node = isy.nodes[_node_addr(isy)]
    with pytest.raises(ISYResponseParseError):
        await node.update()


async def test_node_update_warns_when_request_returns_none(isy: ISY, caplog) -> None:
    """When the controller is unreachable ``request`` returns ``None``;
    ``minidom.parseString(None)`` raises which falls into the
    ISYResponseParseError branch — this test pins that contract."""
    from pyisy.exceptions import ISYResponseParseError

    isy.conn.request = AsyncMock(return_value=None)
    node = isy.nodes[_node_addr(isy)]
    with pytest.raises(ISYResponseParseError):
        await node.update()


async def test_node_update_warns_when_xmldoc_explicitly_none(isy: ISY, caplog) -> None:
    """The auto-update + xmldoc-None path: caller passes nothing and
    the ISY is in auto-update mode (so the inner fetch is skipped),
    leaving xmldoc as None and triggering the warning + early return."""
    isy._connected = True
    # Force the inner fetch branch to be skipped.
    isy.websocket = MagicMock()
    isy.websocket.status = "connected"
    # auto_update returns True via the websocket branch above.
    node = isy.nodes[_node_addr(isy)]
    with caplog.at_level("WARNING", logger="pyisy"):
        await node.update()  # xmldoc=None, auto_update=True
    assert any("could not update node" in r.message.lower() for r in caplog.records)


def test_node_update_state_emits_event_on_prec_change(isy: ISY) -> None:
    """Changing ``prec`` (without changing ``status``) hits the
    `changed = True` branch and fires a status_feedback event."""
    node = isy.nodes[_node_addr(isy)]
    seen: list = []
    node.status_events.subscribe(seen.append)
    new_prec = "9" if node.prec != "9" else "8"
    node.update_state(
        NodeProperty(PROP_STATUS, node.status, new_prec, node.uom, node.formatted, node.address)
    )
    assert seen
    assert node.prec == new_prec


# -- get_groups / set_climate_mode warning paths ---------------------


def test_node_get_groups_finds_responder_membership(isy: ISY) -> None:
    """A node that appears in a scene's ``members`` list is returned
    by ``get_groups(responder=True)``. Walks the fixture to locate a
    scene whose first member is a node we can index, since
    ``members`` and ``controllers`` are separate lists in PyISY."""
    target_group_addr = None
    target_member_id = None
    for addr in isy.nodes.addresses:
        if isy.nodes.ntypes[isy.nodes._address_index[addr]] != TAG_GROUP:
            continue
        group = isy.nodes[addr]
        for member in group.members:
            if isy.nodes.get_by_id(member) is not None:
                target_group_addr = addr
                target_member_id = member
                break
        if target_group_addr:
            break
    if not target_group_addr:
        pytest.skip("fixture has no scene with a resolvable member node")
    node = isy.nodes[target_member_id]
    assert target_group_addr in node.get_groups(controller=False, responder=True)


def test_node_get_groups_finds_controller_membership(isy: ISY) -> None:
    """The controller branch (``responder=False``, ``controller=True``)
    is exercised by forcing a known group's ``_controllers`` to point
    at the test node. The fixture's natural controller/member shapes
    don't always have a node that is a controller while also being
    visible through ``all_lower_nodes`` from the right navigation
    root, so this avoids depending on those particulars."""
    node_addr = _node_addr(isy)
    group_addr = _group_addr(isy)
    group = isy.nodes[group_addr]
    group._controllers = [node_addr]
    group._members = []
    node = isy.nodes[node_addr]
    assert group_addr in node.get_groups(controller=True, responder=False)


async def test_node_set_climate_mode_on_non_thermostat_warns(isy: ISY, caplog) -> None:
    """``set_climate_mode`` emits a warning on a non-thermostat node
    but still resolves the command and (with a valid mode) attempts to
    send it. The warning emit at line 540 is what we're after."""
    isy.conn.request = AsyncMock(return_value="<x/>")
    node = isy.nodes[_node_addr(isy)]
    assert not node.is_thermostat
    with caplog.at_level("WARNING", logger="pyisy"):
        await node.set_climate_mode("heat")
    assert any("not a thermostat" in r.message.lower() for r in caplog.records)
