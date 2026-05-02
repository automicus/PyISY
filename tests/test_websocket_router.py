"""Router tests for :class:`pyisy.events.websocket.WebSocketClient`.

Replays sanitized wire-format events captured from a real eisy stream
through ``_route_message``; asserts each event is dispatched to the
right manager method on ``ISY``. The lifecycle / aiohttp connect loop
is out of scope here — those need a websocket scaffold and live in a
separate module.
"""

from __future__ import annotations

import re
from datetime import UTC
from unittest.mock import MagicMock

import pytest

from pyisy.constants import (
    ES_CONNECTED,
    ES_DISCONNECTED,
)
from pyisy.events.websocket import WebSocketClient

from .conftest import load_events

# -- fixtures ----------------------------------------------------------


@pytest.fixture
def captured_events() -> list[str]:
    return load_events()


def _by_signature(
    events: list[str], control: str, action: str | None = None, must_contain: str | None = None
) -> str:
    """Pick the first captured event matching the given control/action.

    Used so tests can name what they want (``"_1" action=6``) instead of
    hardcoding event indices that shift when the fixture is regenerated.
    """
    for ev in events:
        cm = re.search(r"<control>([^<]*)</control>", ev)
        am = re.search(r"<action[^>]*>([^<]*)</action>", ev)
        if cm and cm.group(1) == control and (action is None or (am and am.group(1) == action)):
            if must_contain is None or must_contain in ev:
                return ev
    pytest.fail(f"no captured event matches control={control!r} action={action!r} contains={must_contain!r}")


@pytest.fixture
def stub_isy():
    """An ``ISY``-shaped object with every manager method that the router
    might call replaced by a ``MagicMock`` we can assert against.

    We don't need a real ``ISY`` here — building the real object would
    pull in a full ``initialize()`` cycle. The router only ever pokes
    these specific attributes."""
    isy = MagicMock()
    isy.nodes = MagicMock()
    isy.programs = MagicMock()
    isy.variables = MagicMock()
    isy.connection_events = MagicMock()
    isy.system_status_changed_received = MagicMock()
    # programs.update is awaited by the router's "fallback program reload"
    # branch; AsyncMock-style return.
    isy.programs.update = MagicMock(side_effect=_async_noop)
    return isy


async def _async_noop(*args, **kwargs):
    return None


@pytest.fixture
async def ws_client(stub_isy) -> WebSocketClient:
    """A ``WebSocketClient`` wired to the stub ISY. The websession is a
    bare mock — these tests never call ``ws_connect``, only the message
    router and a couple of pure-logic helpers.

    Async because ``WebSocketClient.__init__`` calls
    ``asyncio.get_running_loop()`` to capture the event loop for later
    reconnect timer scheduling."""
    return WebSocketClient(
        isy=stub_isy,
        address="127.0.0.1",
        port=80,
        username="u",
        password="p",
        websession=MagicMock(),
    )


# -- fixture sanity check ---------------------------------------------


def test_fixture_has_full_router_branch_coverage(captured_events: list[str]) -> None:
    """Guard against the events fixture losing variety after a re-capture
    /re-anonymization. Every router branch we test below has at least one
    representative event."""
    sigs = {
        (m.group(1), am.group(1) if am else "")
        for ev in captured_events
        for m in [re.search(r"<control>([^<]*)</control>", ev)]
        for am in [re.search(r"<action[^>]*>([^<]*)</action>", ev)]
        if m
    }
    required = {
        ("ST", "0"),
        ("RR", "26"),
        ("OL", "255"),
        ("_0", "90"),
        ("_5", "1"),
        ("_3", "WH"),
        ("_7", "1"),
        ("_1", "0"),
        ("_1", "6"),
        ("_1", "7"),
        ("_1", "8"),
    }
    missing = required - sigs
    assert not missing, f"events fixture is missing branches: {missing}"


# -- ST / OL / RR / ERR -----------------------------------------------


async def test_route_status_event_dispatches_to_nodes_update(
    ws_client: WebSocketClient, captured_events: list[str], stub_isy
) -> None:
    ev = _by_signature(captured_events, "ST")
    await ws_client._route_message(ev)
    stub_isy.nodes.update_received.assert_called_once()
    stub_isy.nodes.control_message_received.assert_not_called()


@pytest.mark.parametrize("control", ["RR", "OL", "ERR"])
async def test_route_control_event_dispatches_to_control_message_received(
    ws_client: WebSocketClient, captured_events: list[str], stub_isy, control: str
) -> None:
    ev = _by_signature(captured_events, control)
    await ws_client._route_message(ev)
    stub_isy.nodes.control_message_received.assert_called_once()
    stub_isy.nodes.update_received.assert_not_called()


# -- heartbeat ---------------------------------------------------------


async def test_route_heartbeat_updates_lasthb_and_hbwait(
    ws_client: WebSocketClient, captured_events: list[str], stub_isy
) -> None:
    """``_0`` events carry the heartbeat interval in ``<action>``; the
    captured fixture has action=90."""
    ev = _by_signature(captured_events, "_0")
    assert ws_client._lasthb is None
    await ws_client._route_message(ev)
    assert ws_client._lasthb is not None
    assert ws_client._hbwait == 90
    # Heartbeat also re-notifies status to the connection_events emitter.
    stub_isy.connection_events.notify.assert_called()


# -- system status -----------------------------------------------------


@pytest.mark.parametrize("action", ["0", "1"])
async def test_route_system_status_dispatches_to_isy_handler(
    ws_client: WebSocketClient, captured_events: list[str], stub_isy, action: str
) -> None:
    ev = _by_signature(captured_events, "_5", action=action)
    await ws_client._route_message(ev)
    stub_isy.system_status_changed_received.assert_called_once()


# -- node-changed (_3) and progress-report (_7) ------------------------


async def test_route_node_changed_dispatches_to_node_changed_received(
    ws_client: WebSocketClient, captured_events: list[str], stub_isy
) -> None:
    ev = _by_signature(captured_events, "_3", action="WH")
    await ws_client._route_message(ev)
    stub_isy.nodes.node_changed_received.assert_called_once()


async def test_route_progress_report_dispatches_to_progress_report_received(
    ws_client: WebSocketClient, captured_events: list[str], stub_isy
) -> None:
    ev = _by_signature(captured_events, "_7")
    await ws_client._route_message(ev)
    stub_isy.nodes.progress_report_received.assert_called_once()


# -- _1 trigger updates ------------------------------------------------


@pytest.mark.parametrize("action", ["6", "7"])
async def test_route_variable_event_dispatches_to_variables_update_received(
    ws_client: WebSocketClient, captured_events: list[str], stub_isy, action: str
) -> None:
    """``_1`` with ``<var>`` payload — captured fixture has both action=6
    (value change) and action=7 (init change)."""
    ev = _by_signature(captured_events, "_1", action=action, must_contain="<var ")
    await ws_client._route_message(ev)
    stub_isy.variables.update_received.assert_called_once()
    stub_isy.programs.update_received.assert_not_called()


async def test_route_program_event_dispatches_to_programs_update_received(
    ws_client: WebSocketClient, captured_events: list[str], stub_isy
) -> None:
    """``_1`` with ``<id>`` payload — fixture has action=0 program updates."""
    ev = _by_signature(captured_events, "_1", action="0", must_contain="<id>")
    await ws_client._route_message(ev)
    stub_isy.programs.update_received.assert_called_once()
    stub_isy.variables.update_received.assert_not_called()


async def test_route_program_key_action_captures_program_key(
    ws_client: WebSocketClient, captured_events: list[str]
) -> None:
    """``_1`` with action=8 (``ACTION_KEY``) is the admin-console "use
    program key" event; the router stores the hex eventInfo as
    ``_program_key`` for downstream programs to read."""
    ev = _by_signature(captured_events, "_1", action="8")
    await ws_client._route_message(ev)
    assert ws_client._program_key == "E8E7BC14.2B06"


async def test_route_program_key_changed_action_captures_node_address(
    ws_client: WebSocketClient,
) -> None:
    """``ACTION_KEY_CHANGED`` (action=2) wasn't in the live capture (rare
    admin-console event); hand-crafted to match the documented schema:
    address goes in ``<node>``, programs reload follows."""
    addr = "12 34 56 1"
    ev = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<Event seqnum="999" sid="uuid:test-session"><control>_1</control>'
        f"<action>2</action><node>{addr}</node><eventInfo></eventInfo></Event>"
    )
    await ws_client._route_message(ev)
    assert ws_client._program_key == addr


async def test_route_unknown_action_triggers_program_reload(ws_client: WebSocketClient, stub_isy) -> None:
    """``_1`` with an unrecognized action and no ``<var>``/``<id>`` /
    ``[`` falls through to ``programs.update()`` — the router's "if
    something changed and we don't know what, refresh programs"
    fallback. Hand-crafted to hit just this branch."""
    ev = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Event seqnum="999" sid="uuid:test-session"><control>_1</control>'
        "<action>5</action><node></node><eventInfo>opaque</eventInfo></Event>"
    )
    await ws_client._route_message(ev)
    stub_isy.programs.update.assert_called_once()


async def test_route_node_server_duplicate_is_silently_ignored(
    ws_client: WebSocketClient, captured_events: list[str], stub_isy
) -> None:
    """``_1`` with ``[`` in eventInfo is the documented "node-server
    duplicate update" silent branch. Captured fixture has action=3
    events with ``[VAR ...]`` content."""
    ev = _by_signature(captured_events, "_1", action="3")
    await ws_client._route_message(ev)
    stub_isy.variables.update_received.assert_not_called()
    stub_isy.programs.update_received.assert_not_called()
    stub_isy.programs.update.assert_not_called()


# -- unknown / malformed inputs ---------------------------------------


@pytest.mark.parametrize("control", ["_4", "_22", "_25", "_26", "_28"])
async def test_route_unknown_underscore_control_silently_ignored(
    ws_client: WebSocketClient, captured_events: list[str], stub_isy, control: str
) -> None:
    """ISY firmware emits various ``_NN`` events the router doesn't claim
    (energy, scheduler, etc.). They must not crash and must not invoke
    any node/program/variable handler — just no-op."""
    ev = _by_signature(captured_events, control)
    await ws_client._route_message(ev)
    stub_isy.nodes.update_received.assert_not_called()
    stub_isy.nodes.control_message_received.assert_not_called()
    stub_isy.variables.update_received.assert_not_called()
    stub_isy.programs.update_received.assert_not_called()


async def test_route_malformed_xml_logs_warning_and_returns(
    ws_client: WebSocketClient, stub_isy, caplog
) -> None:
    with caplog.at_level("WARNING", logger="pyisy.events.websocket"):
        await ws_client._route_message("<not really xml")
    assert any("malformed" in r.message.lower() for r in caplog.records)
    stub_isy.nodes.update_received.assert_not_called()


async def test_route_event_with_empty_control_returns(ws_client: WebSocketClient, stub_isy) -> None:
    ev = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Event seqnum="1"><control></control><action>0</action>'
        "<node></node></Event>"
    )
    await ws_client._route_message(ev)
    stub_isy.nodes.update_received.assert_not_called()


# -- session-id capture (first message) --------------------------------


async def test_sid_captured_on_first_event(ws_client: WebSocketClient, captured_events: list[str]) -> None:
    """The first event with ``sid="..."`` populates ``_sid``; subsequent
    events leave it alone."""
    assert ws_client._sid is None
    # Any captured event has ``sid="uuid:test-session"`` after sanitization.
    ev = captured_events[0]
    await ws_client._route_message(ev)
    assert ws_client._sid == "uuid:test-session"

    # A second event must not overwrite it (router only captures when sid
    # is None).
    ws_client._sid = "uuid:original"
    await ws_client._route_message(ev)
    assert ws_client._sid == "uuid:original"


# -- pure-logic helpers ------------------------------------------------


async def test_status_setter_only_notifies_on_change(ws_client: WebSocketClient, stub_isy) -> None:
    stub_isy.connection_events.notify.reset_mock()
    ws_client.status = ES_CONNECTED
    ws_client.status = ES_CONNECTED  # no-op
    ws_client.status = ES_DISCONNECTED
    assert stub_isy.connection_events.notify.call_count == 2


async def test_heartbeat_time_zero_when_no_lasthb(ws_client: WebSocketClient) -> None:
    assert ws_client._lasthb is None
    assert ws_client.heartbeat_time == 0.0


async def test_last_heartbeat_property_returns_lasthb(ws_client: WebSocketClient) -> None:
    from datetime import datetime

    sentinel = datetime(2026, 5, 2, 12, 0, 0, tzinfo=UTC)
    ws_client._lasthb = sentinel
    assert ws_client.last_heartbeat is sentinel
