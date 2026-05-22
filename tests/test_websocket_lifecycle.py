"""Lifecycle tests for :class:`pyisy.events.websocket.WebSocketClient`.

Complements ``test_websocket_router.py`` (which only exercises the
message-routing path) by covering ``start``/``stop`` task management,
the ``_reconnect`` family, the heartbeat watchdog (``_websocket_guardian``),
and the exception branches in the main ``websocket`` coroutine.

The aiohttp websocket is faked with stand-ins that mimic
``async with session.ws_connect(...) as ws: async for msg in ws``;
no real I/O is performed."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import aiohttp
import pytest

from pyisy.constants import (
    ES_CONNECTED,
    ES_DISCONNECTED,
    ES_INITIALIZING,
    ES_LOST_STREAM_CONNECTION,
    ES_NOT_STARTED,
    ES_RECONNECTING,
    ES_STOP_UPDATES,
    ES_SYNCING,
)
from pyisy.events import websocket as ws_module
from pyisy.events.websocket import WS_MAX_RETRIES, WebSocketClient

# -- fixtures ---------------------------------------------------------


@pytest.fixture
def stub_isy():
    isy = MagicMock()
    isy.connection_events = MagicMock()
    return isy


@pytest.fixture
async def ws_client(stub_isy) -> WebSocketClient:
    return WebSocketClient(
        isy=stub_isy,
        address="127.0.0.1",
        port=80,
        username="u",
        password="p",
        websession=MagicMock(),
    )


# -- heartbeat_time ---------------------------------------------------


def test_heartbeat_time_zero_when_no_heartbeat(ws_client: WebSocketClient) -> None:
    assert ws_client.heartbeat_time == 0.0


def test_heartbeat_time_returns_seconds_since_last(ws_client: WebSocketClient) -> None:
    """Sets ``_lasthb`` 5s in the past and asserts the property reports
    a non-negative seconds delta."""
    ws_client._lasthb = datetime.now() - timedelta(seconds=5)
    elapsed = ws_client.heartbeat_time
    assert isinstance(elapsed, int)
    assert elapsed >= 4  # allow scheduling jitter


# -- start / stop -----------------------------------------------------


@pytest.mark.filterwarnings("ignore::RuntimeWarning")
async def test_start_when_not_connected_creates_tasks(ws_client: WebSocketClient) -> None:
    """``start`` flips status to INITIALIZING and schedules both the
    main websocket task and the guardian task."""
    # Make the inner coroutines no-ops so the tasks complete fast.
    # Use side_effect (not return_value) so each invocation gets a
    # fresh coroutine object and we never leak an unawaited one.
    with (
        patch.object(WebSocketClient, "websocket", side_effect=lambda *a, **kw: _async_noop_coro()),
        patch.object(WebSocketClient, "_websocket_guardian", side_effect=lambda *a, **kw: _async_noop_coro()),
    ):
        ws_client.start()
        assert ws_client.status == ES_INITIALIZING
        assert ws_client.websocket_task is not None
        assert ws_client.guardian_task is not None
        # Drain so we don't leak pending tasks across tests.
        await asyncio.gather(ws_client.websocket_task, ws_client.guardian_task, return_exceptions=True)


async def test_start_is_noop_when_already_connected(ws_client: WebSocketClient) -> None:
    """If already connected, ``start`` returns without scheduling new
    tasks (avoids piling up duplicate websocket coroutines on a noisy
    reconnect path)."""
    ws_client._status = ES_CONNECTED
    ws_client.start()
    assert ws_client.websocket_task is None
    assert ws_client.guardian_task is None


async def test_stop_cancels_all_tasks_and_timer(ws_client: WebSocketClient) -> None:
    """``stop`` cancels the websocket task, the guardian task, and any
    pending reconnect timer; status moves to STOP_UPDATES."""
    ws_client.websocket_task = asyncio.create_task(_sleep_forever())
    ws_client.guardian_task = asyncio.create_task(_sleep_forever())
    timer = MagicMock()
    ws_client._reconnect_timer = timer

    ws_client.stop()
    # Drain so the cancellation actually completes before we check.
    await asyncio.gather(ws_client.websocket_task, ws_client.guardian_task, return_exceptions=True)

    assert ws_client.status == ES_STOP_UPDATES
    assert ws_client.websocket_task.cancelled()
    assert ws_client.guardian_task.cancelled()
    assert ws_client._lasthb is None
    timer.cancel.assert_called_once()
    assert ws_client._reconnect_timer is None


# -- _reconnect family ------------------------------------------------


def test_reconnect_prepare_sets_reconnecting_and_returns_backoff(ws_client: WebSocketClient) -> None:
    delay = ws_client._reconnect_prepare(delay=None, retries=0)
    assert ws_client.status == ES_RECONNECTING
    assert delay > 0


def test_reconnect_prepare_uses_explicit_delay(ws_client: WebSocketClient) -> None:
    """Passing an explicit delay short-circuits the backoff lookup so
    the caller can override (used by the sync reconnect path)."""
    assert ws_client._reconnect_prepare(delay=2.5, retries=0) == 2.5


def test_reconnect_execute_increments_retries_and_starts(ws_client: WebSocketClient) -> None:
    """After backoff completes, ``_reconnect_execute`` calls ``start``
    with retries+1 (clamped at ``WS_MAX_RETRIES``)."""
    with patch.object(WebSocketClient, "start") as start:
        ws_client._reconnect_execute(retries=0)
        start.assert_called_once_with(1)


def test_reconnect_execute_clamps_retries_at_max(ws_client: WebSocketClient) -> None:
    with patch.object(WebSocketClient, "start") as start:
        ws_client._reconnect_execute(retries=WS_MAX_RETRIES + 5)
        start.assert_called_once_with(WS_MAX_RETRIES)


def test_reconnect_schedules_call_later_when_delay_present(ws_client: WebSocketClient) -> None:
    """The sync ``_reconnect`` defers to ``loop.call_later`` for the
    backoff delay rather than awaiting — it's invoked from non-async
    contexts (e.g. the guardian sees a missed heartbeat)."""
    fake_loop = MagicMock()
    ws_client._loop = fake_loop
    with patch.object(WebSocketClient, "_reconnect_prepare", return_value=1.5):
        ws_client._reconnect(retries=0)
    fake_loop.call_later.assert_called_once()
    assert fake_loop.call_later.call_args.args[0] == 1.5


def test_reconnect_runs_immediately_when_delay_falsy(ws_client: WebSocketClient) -> None:
    """A zero/None delay short-circuits the timer and calls
    ``_reconnect_execute`` directly."""
    with (
        patch.object(WebSocketClient, "_reconnect_prepare", return_value=0),
        patch.object(WebSocketClient, "_reconnect_execute") as execute,
    ):
        ws_client._reconnect(retries=2)
    execute.assert_called_once_with(2)


# -- _websocket_guardian ----------------------------------------------


async def test_guardian_triggers_reconnect_when_heartbeat_missed(ws_client: WebSocketClient) -> None:
    """The guardian wakes every ``_hbwait`` seconds. If the websocket
    task has finished (e.g. the connection dropped), it flips status
    to LOST_STREAM_CONNECTION and calls ``_reconnect``."""
    ws_client._hbwait = 0  # don't actually sleep
    # Pretend the websocket task already completed.
    completed = asyncio.create_task(_async_noop_coro())
    await completed
    ws_client.websocket_task = completed
    with patch.object(WebSocketClient, "_reconnect") as reconnect:
        await ws_client._websocket_guardian()
    assert ws_client.status == ES_LOST_STREAM_CONNECTION
    reconnect.assert_called_once()


async def test_guardian_exits_cleanly_on_stop(ws_client: WebSocketClient) -> None:
    """If status is already ``ES_STOP_UPDATES`` the guardian loop
    exits without trying to reconnect."""
    ws_client._status = ES_STOP_UPDATES
    with patch.object(WebSocketClient, "_reconnect") as reconnect:
        await ws_client._websocket_guardian()
    reconnect.assert_not_called()


# -- websocket() main coroutine ---------------------------------------


class _FakeWS:
    """Stand-in for ``aiohttp.ClientWebSocketResponse``.

    Yields a scripted sequence of ``msg`` objects, then completes the
    ``async for``. ``exception()`` and ``close_code`` mimic the real
    surface so the post-loop branch in ``websocket()`` can read them.

    ``keep_open=True`` leaves the socket blocked (open) after the scripted
    frames drain, until ``close()`` is awaited — this lets a test watch
    the SYNCING -> CONNECTED quiet-window promotion without the read loop
    tearing the socket down first. Each ``__anext__`` suspends once
    (``await asyncio.sleep(0)``) so the sync watcher task gets to run."""

    def __init__(self, messages, exc=None, close_code: int = 1000, keep_open: bool = False) -> None:
        self._messages = list(messages)
        self._exc = exc
        self.close_code = close_code
        self._keep_open = keep_open
        self.closed = False
        self._closed_evt = asyncio.Event()

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.closed:
            raise StopAsyncIteration
        if self._messages:
            await asyncio.sleep(0)
            return self._messages.pop(0)
        if self._keep_open:
            await self._closed_evt.wait()
        raise StopAsyncIteration

    async def close(self) -> None:
        self.closed = True
        self._closed_evt.set()

    def exception(self):
        return self._exc


def _ws_msg(msg_type, data: str = "") -> MagicMock:
    msg = MagicMock()
    msg.type = msg_type
    msg.data = data
    return msg


def _ws_connect_returning(ws):
    """Return a stub ``ws_connect`` that yields ``ws`` from its async
    context manager."""

    class _CM:
        async def __aenter__(self_inner):
            return ws

        async def __aexit__(self_inner, *exc_info):
            return False

    def _ws_connect(*args, **kwargs):
        return _CM()

    return _ws_connect


def _ws_connect_raising(exc):
    def _ws_connect(*args, **kwargs):
        raise exc

    return _ws_connect


async def test_websocket_routes_text_messages_and_warns_on_binary(ws_client: WebSocketClient, caplog) -> None:
    """Text frames flow through ``_route_message``; binary frames log
    a warning; an ERROR frame breaks the loop."""
    ws = _FakeWS(
        messages=[
            _ws_msg(aiohttp.WSMsgType.TEXT, "<x/>"),
            _ws_msg(aiohttp.WSMsgType.BINARY),
            _ws_msg(aiohttp.WSMsgType.ERROR),
        ]
    )
    ws_client.req_session.ws_connect = _ws_connect_returning(ws)
    routed: list[str] = []

    async def _capture(self, msg):
        routed.append(msg)

    with (
        patch.object(WebSocketClient, "_route_message", _capture),
        patch.object(WebSocketClient, "_reconnect"),
        caplog.at_level("WARNING", logger="pyisy"),
    ):
        await ws_client.websocket()

    assert routed == ["<x/>"]
    assert any("binary message" in r.message.lower() for r in caplog.records)


async def test_websocket_handles_cancelled_error(ws_client: WebSocketClient) -> None:
    """``CancelledError`` from a stop() call sets DISCONNECTED and
    returns without scheduling a reconnect."""
    ws_client.req_session.ws_connect = _ws_connect_raising(asyncio.CancelledError())
    with patch.object(WebSocketClient, "_reconnect") as reconnect:
        await ws_client.websocket()
    assert ws_client.status == ES_DISCONNECTED
    reconnect.assert_not_called()


@pytest.mark.parametrize(
    "exc",
    [
        TimeoutError(),
        aiohttp.ClientConnectorError(connection_key=MagicMock(), os_error=OSError("boom")),
        aiohttp.ClientOSError("os err"),
        aiohttp.client_exceptions.ServerDisconnectedError(),
    ],
)
async def test_websocket_falls_through_to_reconnect_on_transient_errors(
    ws_client: WebSocketClient, exc
) -> None:
    """Transient connection failures hit one of the typed except
    branches, then drop into the post-try reconnect at the bottom of
    ``websocket``. Each branch must end up calling ``_reconnect``."""
    ws_client._status = ES_NOT_STARTED  # so the final guard fires
    ws_client.req_session.ws_connect = _ws_connect_raising(exc)
    with patch.object(WebSocketClient, "_reconnect") as reconnect:
        await ws_client.websocket()
    assert ws_client.status == ES_LOST_STREAM_CONNECTION
    reconnect.assert_called_once()


async def test_websocket_handshake_error_logs_and_reconnects(ws_client: WebSocketClient, caplog) -> None:
    """``WSServerHandshakeError`` carries a ``.message`` we want logged
    so users diagnosing config problems can see the controller's
    response."""
    err = aiohttp.client_exceptions.WSServerHandshakeError(
        request_info=MagicMock(),
        history=(),
        status=403,
        message="forbidden",
    )
    ws_client.req_session.ws_connect = _ws_connect_raising(err)
    with patch.object(WebSocketClient, "_reconnect"), caplog.at_level("WARNING", logger="pyisy"):
        await ws_client.websocket()
    assert any("forbidden" in r.message for r in caplog.records)


async def test_websocket_unexpected_exception_logged_and_reconnects(
    ws_client: WebSocketClient, caplog
) -> None:
    """The bare ``except Exception`` is the catch-all so a buggy event
    handler doesn't leave the websocket task wedged. ``logger.exception``
    captures the traceback so the user can file a bug."""
    ws_client.req_session.ws_connect = _ws_connect_raising(RuntimeError("kaboom"))
    with patch.object(WebSocketClient, "_reconnect") as reconnect, caplog.at_level("ERROR", logger="pyisy"):
        await ws_client.websocket()
    reconnect.assert_called_once()


async def test_websocket_else_branch_handles_timeout_exception(ws_client: WebSocketClient, caplog) -> None:
    """When the loop exits cleanly but ``ws.exception()`` carries a
    ``TimeoutError``, the else branch logs at debug — distinct from
    the EofStream and unknown-close-code branches."""
    ws = _FakeWS(messages=[], exc=TimeoutError())
    ws_client.req_session.ws_connect = _ws_connect_returning(ws)
    with patch.object(WebSocketClient, "_reconnect"), caplog.at_level("DEBUG", logger="pyisy"):
        await ws_client.websocket()
    assert any("websocket timeout" in r.message.lower() for r in caplog.records)


async def test_websocket_else_branch_handles_eofstream(ws_client: WebSocketClient, caplog) -> None:
    """``aiohttp.streams.EofStream`` from a clean-loop-exit means the
    server closed the underlying TCP stream; surface that with a
    warning so users see the network angle."""
    ws = _FakeWS(messages=[], exc=aiohttp.streams.EofStream())
    ws_client.req_session.ws_connect = _ws_connect_returning(ws)
    with patch.object(WebSocketClient, "_reconnect"), caplog.at_level("WARNING", logger="pyisy"):
        await ws_client.websocket()
    assert any("network connection" in r.message.lower() for r in caplog.records)


async def test_websocket_else_branch_logs_unexpected_disconnect(ws_client: WebSocketClient, caplog) -> None:
    """When the ``async for`` exits cleanly (no exception in the
    ``try``), the ``else`` branch inspects ``ws.exception()`` /
    ``close_code`` and logs the appropriate diagnostic."""
    ws = _FakeWS(messages=[], close_code=1006)
    ws_client.req_session.ws_connect = _ws_connect_returning(ws)
    with patch.object(WebSocketClient, "_reconnect"), caplog.at_level("WARNING", logger="pyisy"):
        await ws_client.websocket()
    assert any("close" in r.message.lower() or "disconnected" in r.message.lower() for r in caplog.records)


async def test_websocket_skips_reconnect_when_stopped_during_loop(ws_client: WebSocketClient) -> None:
    """If ``stop()`` flips status to STOP_UPDATES while the loop is
    running, the post-try guard skips the reconnect — we don't fight
    a user-initiated shutdown. Simulated by having the loop set the
    status to STOP_UPDATES on the way out via the BINARY-frame
    handler hooked through ``_route_message``."""
    ws = _FakeWS(messages=[_ws_msg(aiohttp.WSMsgType.ERROR)])  # ERROR frame breaks the loop
    ws_client.req_session.ws_connect = _ws_connect_returning(ws)

    # The post-try ``else`` branch runs (no exception), then checks
    # status; flipping it from a side effect on ws.exception() is the
    # cleanest hook. ws.exception() is called inside the else branch.
    def _exception_side_effect():
        ws_client._status = ES_STOP_UPDATES

    ws.exception = _exception_side_effect
    with patch.object(WebSocketClient, "_reconnect") as reconnect:
        await ws_client.websocket()
    reconnect.assert_not_called()


# -- SYNCING quiet-window gate (#512) ---------------------------------


async def test_promote_when_quiet_promotes_after_idle(ws_client: WebSocketClient, monkeypatch) -> None:
    """A silent controller (replay already drained) promotes
    SYNCING -> CONNECTED after a single quiet window."""
    monkeypatch.setattr(ws_module, "WS_SYNC_QUIET_SECONDS", 0.01)
    monkeypatch.setattr(ws_module, "WS_SYNC_MAX_SECONDS", 1.0)
    ws_client._status = ES_SYNCING
    ws_client._frame_count = 3  # frames already received; none arriving now
    await ws_client._promote_when_quiet()
    assert ws_client.status == ES_CONNECTED


async def test_promote_when_quiet_holds_until_replay_drains(ws_client: WebSocketClient, monkeypatch) -> None:
    """While the post-connect replay keeps delivering frames the watcher
    holds SYNCING; once the burst goes quiet it promotes to CONNECTED.
    This is the core guard against spurious triggers on every connect."""
    # QUIET (0.2s) is 20x the replay frame interval (0.01s), so a false
    # "quiet" reading would require the replay task to be starved for a
    # whole window (~20 missed wakeups) -- not a realistic CI stall. The
    # observation window below spans two full quiet windows.
    monkeypatch.setattr(ws_module, "WS_SYNC_QUIET_SECONDS", 0.2)
    monkeypatch.setattr(ws_module, "WS_SYNC_MAX_SECONDS", 5.0)
    ws_client._status = ES_SYNCING
    ws_client._frame_count = 0

    stop = asyncio.Event()

    async def _replay() -> None:
        # Frames arrive far faster than the quiet window, so every sample
        # the watcher takes sees movement -> never quiet.
        while not stop.is_set():
            ws_client._frame_count += 1
            await asyncio.sleep(0.01)

    replay = asyncio.create_task(_replay())
    watcher = asyncio.create_task(ws_client._promote_when_quiet())
    try:
        # Two quiet windows pass while the replay is still busy.
        await asyncio.sleep(0.5)
        assert not watcher.done()
        assert ws_client.status == ES_SYNCING

        # Replay drains -> the next quiet sample promotes to CONNECTED.
        stop.set()
        await replay
        await asyncio.wait_for(watcher, timeout=2.0)
        assert ws_client.status == ES_CONNECTED
    finally:
        stop.set()
        watcher.cancel()


async def test_promote_when_quiet_hard_cap_under_constant_traffic(
    ws_client: WebSocketClient, monkeypatch
) -> None:
    """A perpetually chatty controller (frames never stop) must still
    promote at the WS_SYNC_MAX_SECONDS hard cap rather than stall in
    SYNCING forever."""
    monkeypatch.setattr(ws_module, "WS_SYNC_QUIET_SECONDS", 0.05)
    monkeypatch.setattr(ws_module, "WS_SYNC_MAX_SECONDS", 0.15)
    ws_client._status = ES_SYNCING
    ws_client._frame_count = 0

    stop = asyncio.Event()

    async def _flood() -> None:
        while not stop.is_set():
            ws_client._frame_count += 1
            await asyncio.sleep(0.005)

    flood = asyncio.create_task(_flood())
    try:
        await asyncio.wait_for(ws_client._promote_when_quiet(), timeout=2.0)
        assert ws_client.status == ES_CONNECTED
    finally:
        stop.set()
        await asyncio.gather(flood, return_exceptions=True)


async def test_websocket_holds_syncing_through_replay_then_connects(
    ws_client: WebSocketClient, monkeypatch
) -> None:
    """End-to-end through ``websocket()``: a replayed frame is routed
    (records still update) while the stream stays SYNCING, and CONNECTED
    is only emitted after the quiet window."""
    # A wide quiet window (0.2s) keeps the "still SYNCING" assertion below
    # well clear of the watcher's first post-frame sample -- the routed
    # poll breaks within a few ms, leaving ~0.2s of slack before promotion
    # becomes possible, so a scheduler hiccup can't race it.
    monkeypatch.setattr(ws_module, "WS_SYNC_QUIET_SECONDS", 0.2)
    monkeypatch.setattr(ws_module, "WS_SYNC_MAX_SECONDS", 5.0)
    ws = _FakeWS(messages=[_ws_msg(aiohttp.WSMsgType.TEXT, "<x/>")], keep_open=True)
    ws_client.req_session.ws_connect = _ws_connect_returning(ws)
    routed: list[str] = []

    async def _capture(self, msg):
        routed.append(msg)

    with (
        patch.object(WebSocketClient, "_route_message", _capture),
        patch.object(WebSocketClient, "_reconnect"),
    ):
        task = asyncio.create_task(ws_client.websocket())
        try:
            # Wait for the replayed frame to be routed into state.
            for _ in range(200):
                if routed:
                    break
                await asyncio.sleep(0.005)
            await asyncio.sleep(0)  # flush any same-tick callbacks

            # Replay routed (state synced) but the stream is not yet live.
            assert routed == ["<x/>"]
            assert ws_client.status == ES_SYNCING

            # After the quiet window the stream goes live.
            for _ in range(200):
                if ws_client.status == ES_CONNECTED:
                    break
                await asyncio.sleep(0.01)
            assert ws_client.status == ES_CONNECTED
        finally:
            await ws.close()
            await asyncio.wait_for(task, timeout=2.0)


async def test_websocket_socket_drop_before_quiet_never_connects(
    ws_client: WebSocketClient, monkeypatch
) -> None:
    """If the socket drops before the replay settles, the watcher is
    cancelled in the ``finally`` and CONNECTED is never emitted — a
    connection that never settles must not report itself as live."""
    monkeypatch.setattr(ws_module, "WS_SYNC_QUIET_SECONDS", 5.0)
    monkeypatch.setattr(ws_module, "WS_SYNC_MAX_SECONDS", 10.0)
    ws = _FakeWS(messages=[_ws_msg(aiohttp.WSMsgType.TEXT, "<x/>")])  # drains then closes
    ws_client.req_session.ws_connect = _ws_connect_returning(ws)
    notifications: list[str] = []
    ws_client.isy.connection_events.notify = notifications.append

    async def _capture(self, msg):
        return None

    with (
        patch.object(WebSocketClient, "_route_message", _capture),
        patch.object(WebSocketClient, "_reconnect"),
    ):
        await ws_client.websocket()

    assert ES_SYNCING in notifications
    assert ES_CONNECTED not in notifications
    assert ws_client._sync_task is None  # cancelled in the finally


# -- helpers ----------------------------------------------------------


async def _async_noop_coro() -> None:
    return None


async def _sleep_forever() -> None:
    await asyncio.Event().wait()
