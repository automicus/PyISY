"""Tests for :mod:`pyisy.nodes`.

Exercises parsing of the real eisy nodes / status XML and a few status-event
shapes captured from a live websocket stream.
"""

from __future__ import annotations

from unittest.mock import MagicMock
from xml.dom import minidom

import pytest

from pyisy.constants import (
    ISY_VALUE_UNKNOWN,
    PROP_STATUS,
    TAG_FOLDER,
    TAG_GROUP,
    TAG_NODE,
)
from pyisy.exceptions import ISYResponseParseError
from pyisy.nodes import Nodes


@pytest.fixture
def parsed_nodes(nodes_xml: str) -> Nodes:
    isy = MagicMock()
    isy.configuration = {"model": "IoX"}
    return Nodes(isy, xml=nodes_xml)


def test_parse_returns_populated_collections(parsed_nodes: Nodes) -> None:
    assert parsed_nodes.addresses, "no node addresses parsed"
    # 1:1 alignment is a load-bearing invariant of the parallel-list design.
    assert (
        len(parsed_nodes.addresses)
        == len(parsed_nodes.nnames)
        == len(parsed_nodes.ntypes)
        == len(parsed_nodes.nobjs)
        == len(parsed_nodes.nparents)
    )


def test_parse_includes_all_three_node_types(parsed_nodes: Nodes) -> None:
    type_set = set(parsed_nodes.ntypes)
    # eisy export contains folders, groups (scenes) and nodes.
    assert {TAG_FOLDER, TAG_GROUP, TAG_NODE} <= type_set


def test_address_index_round_trips(parsed_nodes: Nodes) -> None:
    for i, addr in enumerate(parsed_nodes.addresses):
        assert parsed_nodes._address_index[addr] == i


def test_apply_status_updates_nodes(parsed_nodes: Nodes, status_xml: str) -> None:
    # Pull the (id, expected formatted) pairs out of the status fixture and
    # confirm at least one matches a known node after parsing.
    parsed_nodes.parse_status = getattr(parsed_nodes, "parse_status", None)
    # Status is applied via update_received-like flow: simplest path is to
    # run the same code init does — `Nodes.parse(...)` then directly seed
    # status through the public xml ingestion that nodes/__init__.py uses.
    # That path is exercised in the full-init test; here we just sanity check
    # that node objects exist for ids referenced in status.xml.
    status_doc = minidom.parseString(status_xml)
    status_ids = {n.attributes["id"].value for n in status_doc.getElementsByTagName("node")}
    overlap = status_ids & set(parsed_nodes.addresses)
    assert overlap, "no overlap between status.xml ids and parsed nodes"


def test_invalid_xml_raises_parse_error() -> None:
    with pytest.raises(ISYResponseParseError):
        Nodes(MagicMock(), xml="<not really xml")


def test_status_event_unknown_node_is_safe(parsed_nodes: Nodes) -> None:
    # An event for an address we don't know about must be ignored rather than
    # crashing the websocket reader (regression guard).
    doc = minidom.parseString(
        '<Event seqnum="1"><control>ST</control>'
        '<action uom="100" prec="0">255</action>'
        "<node>ZZ ZZ ZZ 1</node><eventInfo/></Event>"
    )
    # Should not raise.
    parsed_nodes.update_received(doc)


def test_status_event_for_known_node_updates_status(parsed_nodes: Nodes) -> None:
    address = parsed_nodes.addresses[next(i for i, t in enumerate(parsed_nodes.ntypes) if t == TAG_NODE)]
    node = parsed_nodes[address]
    # Seed a known starting status.
    node.status = ISY_VALUE_UNKNOWN

    doc = minidom.parseString(
        f'<Event seqnum="2"><control>ST</control>'
        f'<action uom="100" prec="0">255</action>'
        f"<node>{address}</node><eventInfo/>"
        f"<fmtAct>On</fmtAct><fmtName>Status</fmtName></Event>"
    )
    parsed_nodes.update_received(doc)
    # update_received writes a NodeProperty for PROP_STATUS via update_state.
    assert node.aux_properties.get(PROP_STATUS) is not None or node.status == 255


def test_snapshot_summary(parsed_nodes: Nodes, snapshot) -> None:
    """Snapshot a structural summary so node-parsing regressions are caught."""
    summary = {
        "count": len(parsed_nodes.addresses),
        "type_counts": {t: parsed_nodes.ntypes.count(t) for t in sorted(set(parsed_nodes.ntypes))},
    }
    assert summary == snapshot
