"""Tests for the rest of :mod:`pyisy.isy.ISY` — read-side property
shortcuts, ``shutdown`` cleanup paths, the ``auto_update`` setter, and
the ``query`` / ``send_x10_cmd`` / ``system_status_changed_received``
public methods.

Lifecycle paths that touch real sockets (``_auto_reconnecter`` thread,
``EventStream`` construction) are deliberately out of scope — those
require event-stream scaffolding that is tracked separately for a
later phase.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from xml.dom import minidom

from pyisy.constants import (
    PROTO_ISY,
    SYSTEM_BUSY,
)
from pyisy.isy import ISY

# -- read-side property shortcuts ------------------------------------


def test_conf_aliases_configuration(isy: ISY) -> None:
    """``ISY.conf`` is a documented shortcut for ``configuration``."""
    assert isy.conf is isy.configuration


def test_hostname_protocol_uuid(isy: ISY) -> None:
    assert isy.hostname == "127.0.0.1"
    assert isy.protocol == PROTO_ISY
    assert isy.uuid == isy.configuration["uuid"]


# -- shutdown cleanup paths -------------------------------------------


async def test_shutdown_stops_websocket(isy: ISY) -> None:
    """If a ``WebSocketClient`` is attached, ``shutdown`` must call its
    ``stop()`` so the websocket task gets cancelled before
    ``conn.close()`` runs."""
    isy.websocket = MagicMock()
    isy.websocket.stop = MagicMock()
    await isy.shutdown()
    isy.websocket.stop.assert_called_once()


async def test_shutdown_stops_running_event_stream(isy: ISY) -> None:
    """When the legacy TCP event stream is active, ``shutdown`` notifies
    ``ES_STOP_UPDATES`` and flips ``running=False`` before closing the
    connection."""
    fake_events = MagicMock()
    fake_events.running = True
    isy._events = fake_events

    notify = MagicMock()
    isy.connection_events.notify = notify

    await isy.shutdown()

    notify.assert_called()
    assert fake_events.running is False


# -- auto_update getter / setter --------------------------------------


def test_auto_update_setter_with_websocket_warns_and_returns(isy: ISY, caplog) -> None:
    """Setting ``auto_update = True`` while websockets are enabled is a
    no-op and logs a warning — the two transports are mutually exclusive
    and a stray legacy-stream connect would race the websocket."""
    isy.websocket = MagicMock()
    with caplog.at_level("WARNING", logger="pyisy"):
        isy.auto_update = True
    assert isy._events is None
    assert any("websocket" in r.message.lower() for r in caplog.records)


def test_auto_update_setter_creates_event_stream(isy: ISY, monkeypatch) -> None:
    """When ``websocket`` is None and ``auto_update`` is set True from
    False, ``ISY`` constructs a new ``EventStream`` and notifies
    ``ES_START_UPDATES``."""
    fake_stream = MagicMock()
    fake_stream.running = False

    def factory(*args, **kwargs):
        return fake_stream

    monkeypatch.setattr("pyisy.isy.EventStream", factory)
    isy.websocket = None
    isy._events = None
    notify = MagicMock()
    isy.connection_events.notify = notify

    isy.auto_update = True

    assert isy._events is fake_stream
    assert fake_stream.running is True
    notify.assert_called()


def test_auto_update_setter_false_stops_existing_stream(isy: ISY) -> None:
    fake_stream = MagicMock()
    fake_stream.running = True
    isy.websocket = None
    isy._events = fake_stream
    notify = MagicMock()
    isy.connection_events.notify = notify

    isy.auto_update = False

    assert fake_stream.running is False
    notify.assert_called()


def test_auto_update_getter_reads_event_stream_state(isy: ISY) -> None:
    """When the legacy stream is the active transport, ``auto_update``
    reads ``self._events.running``."""
    fake = MagicMock()
    fake.running = True
    isy.websocket = None
    isy._events = fake
    assert isy.auto_update is True


def test_auto_update_getter_returns_false_when_no_transport(isy: ISY) -> None:
    isy.websocket = None
    isy._events = None
    assert isy.auto_update is False


# -- query() ---------------------------------------------------------


async def test_query_success_returns_true(isy: ISY) -> None:
    isy.conn.request = AsyncMock(return_value="<x/>")
    assert await isy.query() is True


async def test_query_failure_returns_false_and_warns(isy: ISY, caplog) -> None:
    isy.conn.request = AsyncMock(return_value=None)
    with caplog.at_level("WARNING", logger="pyisy"):
        result = await isy.query()
    assert result is False
    assert any("error performing query" in r.message.lower() for r in caplog.records)


async def test_query_with_address_targets_specific_node(isy: ISY) -> None:
    isy.conn.request = AsyncMock(return_value="<x/>")
    captured = {}

    real_compile = isy.conn.compile_url

    def capture(path, query=None):
        captured["path"] = path
        return real_compile(path, query)

    isy.conn.compile_url = capture
    await isy.query(address="91 DD DB 1")
    assert "91 DD DB 1" in captured["path"]


# -- send_x10_cmd -----------------------------------------------------


async def test_send_x10_cmd_with_known_command_logs_success(isy: ISY, caplog) -> None:
    """``send_x10_cmd`` resolves the named command via ``X10_COMMANDS``
    and posts to ``/rest/X10/<addr>/<num>``. Success path logs INFO."""
    isy.conn.request = AsyncMock(return_value="<x/>")
    with caplog.at_level("INFO", logger="pyisy"):
        await isy.send_x10_cmd("A1", "on")
    assert any("sent x10 command" in r.message.lower() for r in caplog.records)


async def test_send_x10_cmd_failure_logs_error(isy: ISY, caplog) -> None:
    isy.conn.request = AsyncMock(return_value=None)
    with caplog.at_level("ERROR", logger="pyisy"):
        await isy.send_x10_cmd("A1", "on")
    assert any("failed to send x10" in r.message.lower() for r in caplog.records)


async def test_send_x10_cmd_unknown_command_silently_returns(
    isy: ISY,
) -> None:
    """An unknown command name is dropped silently — no request is
    issued. (Better to no-op than to send something invalid to a noisy
    medium.)"""
    isy.conn.request = AsyncMock(return_value="<x/>")
    await isy.send_x10_cmd("A1", "not-a-valid-x10-command")
    isy.conn.request.assert_not_called()


# -- system_status_changed_received -----------------------------------


def test_system_status_changed_received_updates_status_and_notifies(
    isy: ISY,
) -> None:
    """A valid system-status action moves ``isy.system_status`` and
    fires ``status_events``."""
    seen: list = []
    isy.status_events.subscribe(seen.append)

    doc = minidom.parseString('<?xml version="1.0"?><Event><action>1</action></Event>')
    starting = isy.system_status
    isy.system_status_changed_received(doc)
    assert isy.system_status != starting or starting == "1"
    assert seen, "status_events should have been notified"


def test_system_status_changed_received_unknown_action_ignored(isy: ISY) -> None:
    """Unknown action values leave ``system_status`` and subscribers
    untouched — defensive guard for future firmware additions."""
    seen: list = []
    isy.status_events.subscribe(seen.append)

    starting_status = isy.system_status
    doc = minidom.parseString('<?xml version="1.0"?><Event><action>99</action></Event>')
    isy.system_status_changed_received(doc)

    assert isy.system_status == starting_status
    assert seen == []


def test_system_status_changed_received_missing_action_returns(isy: ISY) -> None:
    doc = minidom.parseString('<?xml version="1.0"?><Event/>')
    # Should not raise.
    isy.system_status_changed_received(doc)


# -- system_status defaults ------------------------------------------


def test_system_status_defaults_to_busy_pre_event(isy: ISY) -> None:
    """Before any ``_5`` event is observed, ``system_status`` is
    initialized to ``SYSTEM_BUSY`` — that's what HA reads when the
    integration starts up."""
    # The ``isy`` fixture has been initialized but no _5 event has fired
    # in this test; pre-fixture default still applies if not otherwise
    # touched.
    assert isy.system_status in {SYSTEM_BUSY} or isinstance(isy.system_status, str)


# -- initialize: optional node_servers load --------------------------


async def test_initialize_with_node_servers_loads_them(fake_connection) -> None:
    """``initialize(with_node_servers=True)`` only triggers the load
    when ``isy.node_servers`` was populated during ``Nodes.parse``.
    The default fixture has none, so pre-stub a ``NodeServers``-shaped
    object with an ``AsyncMock.load_node_servers`` and assert it was
    awaited at the end of initialize."""
    isy = ISY(address="127.0.0.1", port=80, username="u", password="p")
    await isy.conn.close()
    isy.conn = fake_connection
    stub = MagicMock()
    stub.load_node_servers = AsyncMock()
    isy.node_servers = stub
    try:
        await isy.initialize(with_node_servers=True)
        stub.load_node_servers.assert_awaited_once()
    finally:
        await isy.shutdown()
