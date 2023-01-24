"""ISY Event Stream."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
from io import TextIOWrapper
import logging
import socket
import ssl
from threading import Thread, ThreadError
import time
from typing import TYPE_CHECKING, Any, cast

from pyisy.connection import ISYConnectionInfo
from pyisy.constants import POLL_TIME, RECONNECT_DELAY, EventStreamStatus
from pyisy.events import strings
from pyisy.events.eventreader import ISYEventReader
from pyisy.events.router import EventRouter
from pyisy.exceptions import ISYInvalidAuthError, ISYMaxConnections, ISYStreamDataError

if TYPE_CHECKING:
    from pyisy.isy import ISY

SOCKET_HEARTBEAT = 30
SOCKET_HB_GRACE = 5

_LOGGER = logging.getLogger(__name__)  # Allows targeting pyisy.events in handlers.


class EventStream:
    """Class to represent the Event Stream from the ISY."""

    isy: ISY
    connection_info: ISYConnectionInfo
    _on_lost_function: Callable | None = None
    _running: bool = False
    _thread: Thread | None
    _last_heartbeat: datetime | None = None
    _heartbeat_interval: int = SOCKET_HEARTBEAT
    _status: str = EventStreamStatus.NOT_STARTED
    _stream_id: str = ""
    _program_key: str = ""
    _connected: bool = False
    _subscribed: bool = False
    websocket_task: asyncio.Task | None = None
    guardian_task: asyncio.Task | None = None
    router: EventRouter
    socket: socket.socket | ssl.SSLSocket
    cert: Any | None = None
    _writer: TextIOWrapper

    def __init__(
        self,
        isy: ISY,
        connection_info: ISYConnectionInfo,
        on_lost_func: Callable | None = None,
    ) -> None:
        """Initialize the EventStream class."""
        self.isy = isy
        self._on_lost_function = on_lost_func
        self.connection_info = connection_info
        self.router = EventRouter(self)

        # create TLS encrypted socket if we're using HTTPS
        if self.connection_info.use_https:
            tls_ver = self.connection_info.tls_version
            if tls_ver == 1.1:
                context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_1)
            elif tls_ver == 1.2:
                context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
            else:
                context = ssl.SSLContext(ssl.PROTOCOL_TLS)
            context.check_hostname = False
            self.socket = context.wrap_socket(
                socket.socket(socket.AF_INET, socket.SOCK_STREAM),
                server_hostname=self.connection_info.url,
            )
        else:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def _create_message(self, msg: dict[str, str]) -> str:
        """Prepare a message for sending."""
        head: str = msg["head"]
        body: str = msg["body"]
        body = body.format(sid=self._stream_id)
        length = len(body)
        parsed_url = self.connection_info.parsed_url
        head = head.format(
            length=length,
            url=f"{parsed_url[1]}{parsed_url[2]}",
            auth=self.connection_info.auth.encode(),
        )
        return head + body

    def heartbeat(self, interval: int = SOCKET_HEARTBEAT) -> None:
        """Receive a heartbeat from the ISY event thread."""
        if self._status is EventStreamStatus.NOT_STARTED:
            self._status = EventStreamStatus.INITIALIZING
            self.isy.connection_events.notify(EventStreamStatus.INITIALIZING)
        elif self._status == EventStreamStatus.INITIALIZING:
            self._status = EventStreamStatus.LOADED
            self.isy.connection_events.notify(EventStreamStatus.LOADED)
        self._last_heartbeat = datetime.now()
        self._heartbeat_interval = interval
        _LOGGER.debug("ISY HEARTBEAT: %s", self._last_heartbeat.isoformat())
        self.isy.connection_events.notify(self._status)

    def update_stream_id(self, stream_id: str) -> None:
        """Set the socket ID."""
        self._stream_id = stream_id
        _LOGGER.debug("Updated events stream ID: %s", self._stream_id)

    @property
    def running(self) -> bool:
        """Return the running state of the thread."""
        try:
            if self._thread is None:
                return False
            return self._thread.is_alive()
        except (AttributeError, RuntimeError, ThreadError):
            return False

    @running.setter
    def running(self, val: bool) -> None:
        if val and not self.running:
            _LOGGER.info("Starting updates")
            if self.connect():
                self.subscribe()
                self._running = True
                self._thread = Thread(target=self.watch)
                self._thread.daemon = True
                self._thread.start()
        else:
            _LOGGER.info("Stopping updates")
            self._running = False
            self.unsubscribe()
            self.disconnect()

    def write(self, msg: str) -> None:
        """Write data back to the socket."""
        if self._writer is None:
            raise NotImplementedError("Function not available while socket is closed.")
        self._writer.write(msg)
        self._writer.flush()

    def connect(self) -> bool:
        """Connect to the event stream socket."""
        if not self._connected:
            try:
                self.socket.connect(
                    (
                        self.connection_info.parsed_url.hostname,
                        self.connection_info.parsed_url.port,
                    )
                )
                if self.connection_info.tls_version and self.connection_info.use_https:
                    self.cert = cast(ssl.SSLSocket, self.socket).getpeercert()
            except OSError as err:
                _LOGGER.exception(
                    "PyISY could not connect to ISY event stream. %s", err
                )
                if self._on_lost_function is not None:
                    self._on_lost_function()
                return False
            self.socket.setblocking(False)
            self._writer = self.socket.makefile("w")
            self._connected = True
            self.isy.connection_events.notify(EventStreamStatus.CONNECTED)
            return True
        return True

    def disconnect(self) -> None:
        """Disconnect from the Event Stream socket."""
        if not self._connected:
            return
        self.socket.close()
        self._connected = False
        self._subscribed = False
        self._running = False
        self.isy.connection_events.notify(EventStreamStatus.DISCONNECTED)

    def subscribe(self) -> None:
        """Subscribe to the Event Stream."""
        if not self._subscribed and self._connected:
            if self._stream_id == "":
                msg = self._create_message(strings.SUB_MSG)
                self.write(msg)
            else:
                msg = self._create_message(strings.RESUB_MSG)
                self.write(msg)
            self._subscribed = True

    def unsubscribe(self) -> None:
        """Unsubscribe from the Event Stream."""
        if self._subscribed and self._connected:
            msg = self._create_message(strings.UNSUB_MSG)
            try:
                self.write(msg)
            except OSError as ex:
                _LOGGER.error(
                    "PyISY encountered a socket error while writing unsubscribe message to the socket: %s.",
                    ex,
                )
            self._subscribed = False
            self.disconnect()

    @property
    def connected(self) -> bool:
        """Return if the module is connected to the ISY or not."""
        return self._connected

    @property
    def heartbeat_time(self) -> float:
        """Return the last ISY Heartbeat time."""
        if self._last_heartbeat is not None:
            return (datetime.now() - self._last_heartbeat).seconds
        return 0.0

    def _lost_connection(self, delay: int = 0) -> None:
        """React when the event stream connection is lost."""
        _LOGGER.warning("PyISY lost connection to the ISY event stream.")
        self.isy.connection_events.notify(EventStreamStatus.LOST_CONNECTION)
        self.unsubscribe()
        if self._on_lost_function is not None:
            time.sleep(delay)
            self._on_lost_function()

    def watch(self) -> None:
        """Watch the subscription connection and report if dead."""
        if not self._subscribed:
            _LOGGER.debug("PyISY watch called without a subscription.")
            return

        event_reader = ISYEventReader(self.socket)

        while self._running and self._subscribed:
            # verify connection is still alive
            if self.heartbeat_time > self._heartbeat_interval:
                self._lost_connection()
                return

            try:
                events = event_reader.read_events(POLL_TIME)
            except ISYMaxConnections:
                _LOGGER.error(
                    "PyISY reached maximum connections, delaying reconnect attempt by %s seconds.",
                    RECONNECT_DELAY,
                )
                self._lost_connection(RECONNECT_DELAY)
                return
            except ISYInvalidAuthError:
                _LOGGER.error(
                    "Invalid authentication used to connect to the event stream."
                )
                return
            except ISYStreamDataError as ex:
                _LOGGER.warning(
                    "PyISY encountered an error while reading the event stream: %s.", ex
                )
                self._lost_connection()
                return
            except OSError as ex:
                _LOGGER.warning(
                    "PyISY encountered a socket error while reading the event stream: %s.",
                    ex,
                )
                self._lost_connection()
                return

            for message in events:
                try:
                    self.router.parse_message(message)
                except Exception as ex:  # pylint: disable=broad-except
                    _LOGGER.warning(
                        "PyISY encountered while routing message '%s': %s", message, ex
                    )
                    raise

    def __del__(self) -> None:
        """Ensure we unsubscribe on destroy."""
        self.unsubscribe()
