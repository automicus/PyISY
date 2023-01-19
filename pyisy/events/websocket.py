"""ISY Websocket Event Stream."""
import asyncio
import logging
import xml
from xml.dom import minidom

import aiohttp

from ..connection import get_new_client_session, get_sslcontext
from ..constants import (
    ACTION_KEY,
    ACTION_KEY_CHANGED,
    ATTR_ACTION,
    ATTR_CONTROL,
    ATTR_ID,
    ATTR_STREAM_ID,
    ATTR_VAR,
    ES_CONNECTED,
    ES_DISCONNECTED,
    ES_INITIALIZING,
    ES_LOST_STREAM_CONNECTION,
    ES_NOT_STARTED,
    ES_RECONNECTING,
    ES_STOP_UPDATES,
    PROP_STATUS,
    TAG_EVENT_INFO,
    TAG_NODE,
)
from ..helpers import attr_from_xml, now, value_from_xml
from ..logging import LOG_VERBOSE, enable_logging

_LOGGER = logging.getLogger(__name__)  # Allows targeting pyisy.events in handlers.

WS_HEADERS = {
    "Sec-WebSocket-Protocol": "ISYSUB",
    "Sec-WebSocket-Version": "13",
    "Origin": "com.universal-devices.websockets.isy",
}
WS_HEARTBEAT = 30
WS_HB_GRACE = 2
WS_TIMEOUT = 10.0
WS_MAX_RETRIES = 4
WS_RETRY_BACKOFF = [0.01, 1, 10, 30, 60]  # Seconds


class WebSocketClient:
    """Class for handling web socket communications with the ISY."""

    def __init__(
        self,
        isy,
        address,
        port,
        username,
        password,
        use_https=False,
        tls_ver=1.1,
        webroot="",
        websession=None,
    ):
        """Initialize a new Web Socket Client class."""
        if len(_LOGGER.handlers) == 0:
            enable_logging(add_null_handler=True)

        self.isy = isy
        self._address = address
        self._port = port
        self._username = username
        self._password = password
        self._auth = aiohttp.BasicAuth(self._username, self._password)
        self._webroot = webroot.rstrip("/")
        self._tls_ver = tls_ver
        self.use_https = use_https
        self._status = ES_NOT_STARTED
        self._lasthb = None
        self._hbwait = WS_HEARTBEAT
        self._sid = None
        self._program_key = None
        self.websocket_task = None
        self.guardian_task = None

        if websession is None:
            websession = get_new_client_session(use_https, tls_ver)

        self.req_session = websession
        self.sslcontext = get_sslcontext(use_https, tls_ver)
        self._loop = asyncio.get_running_loop()

        self._url = "wss://" if self.use_https else "ws://"
        self._url += f"{self._address}:{self._port}{self._webroot}/rest/subscribe"

    def start(self, retries=0):
        """Start the websocket connection."""
        if self.status != ES_CONNECTED:
            _LOGGER.debug("Starting websocket connection.")
            self.status = ES_INITIALIZING
            self.websocket_task = self._loop.create_task(self.websocket(retries))
            self.guardian_task = self._loop.create_task(self._websocket_guardian())

    def stop(self):
        """Close websocket connection."""
        self.status = ES_STOP_UPDATES
        if self.websocket_task is not None:
            _LOGGER.debug("Stopping websocket connection.")
            self.websocket_task.cancel()
        if self.guardian_task is not None:
            self.guardian_task.cancel()
            self._lasthb = None

    async def reconnect(self, delay=None, retries=0):
        """Reconnect to a disconnected websocket."""
        self.stop()
        self.status = ES_RECONNECTING
        if delay is None:
            delay = WS_RETRY_BACKOFF[retries]
        _LOGGER.info("PyISY attempting stream reconnect in %ss.", delay)
        await asyncio.sleep(delay)
        retries = (retries + 1) if retries < WS_MAX_RETRIES else WS_MAX_RETRIES
        self.start(retries)

    @property
    def status(self):
        """Return if the websocket is running or not."""
        return self._status

    @status.setter
    def status(self, value):
        """Set the current node state and notify listeners."""
        if self._status != value:
            self._status = value
            self.isy.connection_events.notify(self._status)
        return self._status

    @property
    def last_heartbeat(self):
        """Return the last received heartbeat time from the ISY."""
        return self._lasthb

    @property
    def heartbeat_time(self):
        """Return the time since the last ISY Heartbeat."""
        if self._lasthb is not None:
            return (now() - self._lasthb).seconds
        return 0.0

    async def _websocket_guardian(self):
        """Watch and reset websocket connection if no messages received."""
        while self.status != ES_STOP_UPDATES:
            await asyncio.sleep(self._hbwait)
            if (
                self.websocket_task.cancelled()
                or self.websocket_task.done()
                or self.heartbeat_time > self._hbwait + WS_HB_GRACE
            ):
                _LOGGER.debug("Websocket missed a heartbeat, resetting connection.")
                self.status = ES_LOST_STREAM_CONNECTION
                self._loop.create_task(self.reconnect())
                return

    async def _route_message(self, msg):
        """Route a received message from the event stream."""
        # check xml formatting
        try:
            xmldoc = minidom.parseString(msg)
        except xml.parsers.expat.ExpatError:
            _LOGGER.warning("ISY Received Malformed XML:\n%s", msg)
            return
        _LOGGER.log(LOG_VERBOSE, "ISY Update Received:\n%s", msg)

        # A wild stream id appears!
        if f"{ATTR_STREAM_ID}=" in msg and self._sid is None:
            self.update_received(xmldoc)

        # direct the event message
        cntrl = value_from_xml(xmldoc, ATTR_CONTROL)
        if not cntrl:
            return
        if cntrl == "_0":  # ISY HEARTBEAT
            self._lasthb = now()
            self._hbwait = int(value_from_xml(xmldoc, ATTR_ACTION))
            _LOGGER.debug("ISY HEARTBEAT: %s", self._lasthb.isoformat())
            self.isy.connection_events.notify(self._status)
        elif cntrl == PROP_STATUS:  # NODE UPDATE
            self.isy.nodes.update_received(xmldoc)
        elif cntrl[0] != "_":  # NODE CONTROL EVENT
            self.isy.nodes.control_message_received(xmldoc)
        elif cntrl == "_1":  # Trigger Update
            if f"<{ATTR_VAR}" in msg:  # VARIABLE (action=6 or 7)
                self.isy.variables.update_received(xmldoc)
            elif f"<{ATTR_ID}>" in msg:  # PROGRAM (action=0)
                self.isy.programs.update_received(xmldoc)
            elif f"<{TAG_NODE}>" in msg and "[" in msg:  # Node Server Update
                pass  # This is most likely a duplicate node update.
            elif f"<{ATTR_ACTION}>" in msg:
                action = value_from_xml(xmldoc, ATTR_ACTION)
                if action == ACTION_KEY:
                    self._program_key = value_from_xml(xmldoc, TAG_EVENT_INFO)
                    return
                if action == ACTION_KEY_CHANGED:
                    self._program_key = value_from_xml(xmldoc, TAG_NODE)
                # Need to reload programs
                await self.isy.programs.update()
        elif cntrl == "_3":  # Node Changed/Updated
            self.isy.nodes.node_changed_received(xmldoc)
        elif cntrl == "_5":  # System Status Changed
            self.isy.system_status_changed_received(xmldoc)
        elif cntrl == "_7":  # Progress report, device programming event
            self.isy.nodes.progress_report_received(xmldoc)

    def update_received(self, xmldoc):
        """Set the socket ID."""
        self._sid = attr_from_xml(xmldoc, "Event", ATTR_STREAM_ID)
        _LOGGER.debug("ISY Updated Events Stream ID: %s", self._sid)

    async def websocket(self, retries=0):
        """Start websocket connection."""
        try:
            async with self.req_session.ws_connect(
                self._url,
                auth=self._auth,
                heartbeat=WS_HEARTBEAT,
                headers=WS_HEADERS,
                timeout=WS_TIMEOUT,
                receive_timeout=self._hbwait + WS_HB_GRACE,
                ssl=self.sslcontext,
            ) as ws:
                self.status = ES_CONNECTED
                retries = 0
                _LOGGER.debug("Successfully connected to websocket.")

                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        await self._route_message(msg.data)
                    elif msg.type == aiohttp.WSMsgType.BINARY:
                        _LOGGER.warning("Unexpected binary message received.")
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        _LOGGER.error("Error during receive %s", ws.exception())
                        break

        except asyncio.CancelledError:
            self.status = ES_DISCONNECTED
            return
        except asyncio.TimeoutError:
            _LOGGER.debug("Websocket Timeout.")
        except aiohttp.ClientConnectorError as err:
            _LOGGER.error("Websocket Client Connector Error %s", err, exc_info=True)
        except (
            aiohttp.ClientOSError,
            aiohttp.client_exceptions.ServerDisconnectedError,
        ):
            _LOGGER.debug("Websocket Server Not Ready.")
        except aiohttp.client_exceptions.WSServerHandshakeError as err:
            _LOGGER.warning("Web socket server response error: %s", err.message)
        # pylint: disable=broad-except
        except Exception as err:
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
        if self.status != ES_STOP_UPDATES:
            self.status = ES_LOST_STREAM_CONNECTION
            self._loop.create_task(self.reconnect(retries=retries))
