"""ISY Websocket Event Stream."""
from __future__ import annotations

import asyncio
from datetime import datetime
import logging
from typing import TYPE_CHECKING

import aiohttp

from pyisy.connection import ISYConnectionInfo
from pyisy.constants import EventStreamStatus
from pyisy.events.router import EventRouter
from pyisy.helpers.session import get_new_client_session, get_sslcontext
from pyisy.logging import enable_logging

if TYPE_CHECKING:
    from pyisy.isy import ISY


_LOGGER = logging.getLogger(__name__)  # Allows targeting pyisy.events in handlers.

WS_HEADERS = {
    "Sec-WebSocket-Protocol": "ISYSUB",
    "Sec-WebSocket-Version": "13",
    "Origin": "com.universal-devices.websockets.isy",
}
WS_HEARTBEAT = 30
WS_HB_GRACE = 5
WS_TIMEOUT = 10.0
WS_MAX_RETRIES = 4
WS_RETRY_BACKOFF = [0.01, 1, 10, 30, 60]  # Seconds


class WebSocketClient:
    """Class for handling web socket communications with the ISY."""

    isy: ISY
    connection_info: ISYConnectionInfo
    _last_heartbeat: datetime | None = None
    _heartbeat_interval: int = WS_HEARTBEAT
    _status: str = EventStreamStatus.NOT_STARTED
    _stream_id: str = ""
    _program_key: str = ""
    websocket_task: asyncio.Task | None = None
    guardian_task: asyncio.Task | None = None
    router: EventRouter

    def __init__(self, isy: ISY, connection_info: ISYConnectionInfo) -> None:
        """Initialize a new Web Socket Client class."""
        if len(_LOGGER.handlers) == 0:
            enable_logging(add_null_handler=True)

        self.isy = isy
        self.connection_info = connection_info
        self.router = EventRouter(self)

        if connection_info.websession is None:
            connection_info.websession = get_new_client_session(connection_info)

        self.req_session = connection_info.websession
        self.sslcontext = get_sslcontext(connection_info)
        self._loop = asyncio.get_running_loop()

        self._url = connection_info.ws_url

    def start(self, retries: int = 0) -> None:
        """Start the websocket connection."""
        if self.status != EventStreamStatus.CONNECTED:
            _LOGGER.debug("Starting websocket connection.")
            self.status = EventStreamStatus.INITIALIZING
            self.websocket_task = self._loop.create_task(self.websocket(retries))
            self.guardian_task = self._loop.create_task(self._websocket_guardian())

    def stop(self) -> None:
        """Close websocket connection."""
        self.status = EventStreamStatus.STOP_UPDATES
        if self.websocket_task is not None:
            _LOGGER.debug("Stopping websocket connection.")
            self.websocket_task.cancel()
        if self.guardian_task is not None:
            self.guardian_task.cancel()
            self._last_heartbeat = None

    async def reconnect(self, delay: float | None = None, retries: int = 0) -> None:
        """Reconnect to a disconnected websocket."""
        self.stop()
        self.status = EventStreamStatus.RECONNECTING
        if delay is None:
            delay = WS_RETRY_BACKOFF[retries]
        _LOGGER.info("PyISY attempting stream reconnect in %ss.", delay)
        await asyncio.sleep(delay)
        retries = (retries + 1) if retries < WS_MAX_RETRIES else WS_MAX_RETRIES
        self.start(retries)

    @property
    def status(self) -> str:
        """Return if the websocket is running or not."""
        return self._status

    @status.setter
    def status(self, value: str) -> None:
        """Set the current node state and notify listeners."""
        if self._status != value:
            self._status = value
            self.isy.connection_events.notify(self._status)

    @property
    def last_heartbeat(self) -> datetime | None:
        """Return the last received heartbeat time from the ISY."""
        return self._last_heartbeat

    @property
    def heartbeat_time(self) -> float:
        """Return the time since the last ISY Heartbeat."""
        if self._last_heartbeat is not None:
            return (datetime.now() - self._last_heartbeat).seconds
        return 0.0

    async def _websocket_guardian(self) -> None:
        """Watch and reset websocket connection if no messages received."""
        while self.status != EventStreamStatus.STOP_UPDATES:
            await asyncio.sleep(self._heartbeat_interval)
            if (
                self.websocket_task is None
                or self.websocket_task.cancelled()
                or self.websocket_task.done()
                or self.heartbeat_time > self._heartbeat_interval + WS_HB_GRACE
            ):
                _LOGGER.debug("Websocket missed a heartbeat, resetting connection.")
                self.status = EventStreamStatus.LOST_CONNECTION
                self._loop.create_task(self.reconnect())
                return

    def heartbeat(self, interval: int = WS_HEARTBEAT) -> None:
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
        _LOGGER.debug("Updated Events Stream ID: %s", self._stream_id)

    async def websocket(self, retries: int = 0) -> None:
        """Start websocket connection."""
        try:
            async with self.req_session.ws_connect(
                self._url,
                auth=self.connection_info.auth,
                heartbeat=WS_HEARTBEAT,
                headers=WS_HEADERS,
                timeout=WS_TIMEOUT,
                receive_timeout=self._heartbeat_interval + WS_HB_GRACE,
                ssl=self.sslcontext,
            ) as ws:
                self.status = EventStreamStatus.CONNECTED
                retries = 0
                _LOGGER.debug("Successfully connected to websocket.")

                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        self.router.parse_message(msg.data)
                    elif msg.type == aiohttp.WSMsgType.BINARY:
                        _LOGGER.warning("Unexpected binary message received.")
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        _LOGGER.error("Error during receive %s", ws.exception())
                        break

        except asyncio.CancelledError:
            self.status = EventStreamStatus.DISCONNECTED
            return
        except asyncio.TimeoutError:
            _LOGGER.debug("Websocket Timeout.")
        except ConnectionRefusedError:
            _LOGGER.error("Websocket connection refused")
        except aiohttp.client_exceptions.ClientConnectorError as err:
            _LOGGER.error("Websocket Client Connector Error %s", err)
        except (
            aiohttp.ClientOSError,
            aiohttp.client_exceptions.ServerDisconnectedError,
        ):
            _LOGGER.debug("Websocket Server Not Ready.")
        except aiohttp.client_exceptions.WSServerHandshakeError as err:
            _LOGGER.warning("Web socket server response error: %s", err.message)

        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.error("Unexpected websocket error %s", err, exc_info=True)
        else:
            if isinstance(ws.exception(), asyncio.TimeoutError):
                _LOGGER.debug("Websocket Timeout.")
            elif isinstance(ws.exception(), aiohttp.streams.EofStream):
                _LOGGER.warning(
                    "Websocket disconnected unexpectedly. Check network connection."
                )
            else:
                _LOGGER.warning(
                    "Websocket disconnected unexpectedly with code: %s", ws.close_code
                )
        if self.status != EventStreamStatus.STOP_UPDATES:
            self.status = EventStreamStatus.LOST_CONNECTION
            self._loop.create_task(self.reconnect(retries=retries))
