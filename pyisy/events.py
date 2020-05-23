"""ISY Event Stream."""
import asyncio
import logging
import socket
import ssl
from threading import Thread, ThreadError
import time
import xml
from xml.dom import minidom

import aiohttp

from . import strings
from .connection import get_new_client_session, get_sslcontext
from .constants import (
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
    ES_LOADED,
    ES_LOST_STREAM_CONNECTION,
    ES_NOT_STARTED,
    ES_RECONNECTING,
    ES_STOP_UPDATES,
    LOG_DATE_FORMAT,
    LOG_FORMAT,
    LOG_LEVEL,
    LOG_VERBOSE,
    POLL_TIME,
    PROP_STATUS,
    RECONNECT_DELAY,
    TAG_EVENT_INFO,
    TAG_NODE,
)
from .eventreader import ISYEventReader, ISYMaxConnections, ISYStreamDataError
from .helpers import attr_from_xml, now, value_from_xml

_LOGGER = logging.getLogger(__name__)  # Allows targeting pyisy.events in handlers.

WS_HEADERS = {
    "Sec-WebSocket-Protocol": "ISYSUB",
    "Sec-WebSocket-Version": "13",
    "Origin": "com.universal-devices.websockets.isy",
}
WS_HEARTBEAT = 30
WS_TIMEOUT = aiohttp.ClientTimeout(total=60, connect=60, sock_connect=60, sock_read=60)
WS_MAX_RETRIES = 4
WS_RETRY_BACKOFF = [0.01, 1, 10, 30, 60]  # Seconds


class EventStream:
    """Class to represent the Event Stream from the ISY."""

    def __init__(self, isy, connection_info, on_lost_func=None):
        """Initialize the EventStream class."""
        self.isy = isy
        self._running = False
        self._writer = None
        self._thread = None
        self._subscribed = False
        self._connected = False
        self._lasthb = None
        self._hbwait = 0
        self._loaded = None
        self._on_lost_function = on_lost_func
        self.cert = None
        self.data = connection_info

        # create TLS encrypted socket if we're using HTTPS
        if self.data.get("tls") is not None:
            if self.data["tls"] == 1.1:
                context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_1)
            else:
                context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
            context.check_hostname = False
            self.socket = context.wrap_socket(
                socket.socket(socket.AF_INET, socket.SOCK_STREAM),
                server_hostname=f"https://{self.data['addr']}",
            )
        else:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def _create_message(self, msg):
        """Prepare a message for sending."""
        head = msg["head"]
        body = msg["body"]
        body = body.format(**self.data)
        length = len(body)
        head = head.format(length=length, **self.data)
        return head + body

    def _route_message(self, msg):
        """Route a received message from the event stream."""
        # check xml formatting
        try:
            xmldoc = minidom.parseString(msg)
        except xml.parsers.expat.ExpatError:
            _LOGGER.warning("ISY Received Malformed XML:\n" + msg)
            return
        _LOGGER.log(LOG_VERBOSE, "ISY Update Received:\n" + msg)

        # A wild stream id appears!
        if f"{ATTR_STREAM_ID}=" in msg and ATTR_STREAM_ID not in self.data:
            self.update_received(xmldoc)

        # direct the event message
        cntrl = value_from_xml(xmldoc, ATTR_CONTROL)
        if not cntrl:
            return
        if cntrl == "_0":  # ISY HEARTBEAT
            if self._loaded is None:
                self._loaded = ES_INITIALIZING
                self.isy.connection_events.notify(ES_INITIALIZING)
            elif self._loaded == ES_INITIALIZING:
                self._loaded = ES_LOADED
                self.isy.connection_events.notify(ES_LOADED)
            self._lasthb = now()
            self._hbwait = int(value_from_xml(xmldoc, ATTR_ACTION))
            _LOGGER.debug("ISY HEARTBEAT: %s", self._lasthb.isoformat())
        elif cntrl == PROP_STATUS:  # NODE UPDATE
            self.isy.nodes.update_received(xmldoc)
        elif cntrl[0] != "_":  # NODE CONTROL EVENT
            self.isy.nodes.control_message_received(xmldoc)
        elif cntrl == "_1":  # Trigger Update
            if f"<{ATTR_VAR}" in msg:  # VARIABLE
                self.isy.variables.update_received(xmldoc)
            elif f"<{ATTR_ID}>" in msg:  # PROGRAM
                self.isy.programs.update_received(xmldoc)
            elif f"<{TAG_NODE}>" in msg and "[" in msg:  # Node Server Update
                pass  # This is most likely a duplicate node update.
            elif f"<{ATTR_ACTION}>" in msg:
                action = value_from_xml(xmldoc, ATTR_ACTION)
                if action == ACTION_KEY:
                    self.data[ACTION_KEY] = value_from_xml(xmldoc, TAG_EVENT_INFO)
                    return
                if action == ACTION_KEY_CHANGED:
                    self._program_key = value_from_xml(xmldoc, TAG_NODE)
                # Need to reload programs
                asyncio.run_coroutine_threadsafe(
                    self.isy.programs.update(), self.isy.loop
                )
        elif cntrl == "_3":  # Node Changed/Updated
            self.isy.nodes.node_changed_received(xmldoc)

    def update_received(self, xmldoc):
        """Set the socket ID."""
        self.data[ATTR_STREAM_ID] = attr_from_xml(xmldoc, "Event", ATTR_STREAM_ID)
        _LOGGER.debug("ISY Updated Events Stream ID")

    @property
    def running(self):
        """Return the running state of the thread."""
        try:
            return self._thread.isAlive()
        except (AttributeError, RuntimeError, ThreadError):
            return False

    @running.setter
    def running(self, val):
        if val and not self.running:
            _LOGGER.info("ISY Starting Updates")
            if self.connect():
                self.subscribe()
                self._running = True
                self._thread = Thread(target=self.watch)
                self._thread.daemon = True
                self._thread.start()
        else:
            _LOGGER.info("ISY Stopping Updates")
            self._running = False
            self.unsubscribe()
            self.disconnect()

    def write(self, msg):
        """Write data back to the socket."""
        if self._writer is None:
            raise NotImplementedError("Function not available while socket is closed.")
        self._writer.write(msg)
        self._writer.flush()

    def connect(self):
        """Connect to the event stream socket."""
        if not self._connected:
            try:
                self.socket.connect((self.data["addr"], self.data["port"]))
                if self.data.get("tls"):
                    self.cert = self.socket.getpeercert()
            except OSError:
                _LOGGER.error("PyISY could not connect to ISY event stream.")
                if self._on_lost_function is not None:
                    self._on_lost_function()
                return False
            self.socket.setblocking(0)
            self._writer = self.socket.makefile("w")
            self._connected = True
            self.isy.connection_events.notify(ES_CONNECTED)
            return True
        return True

    def disconnect(self):
        """Disconnect from the Event Stream socket."""
        if self._connected:
            self.socket.close()
            self._connected = False
            self._subscribed = False
            self._running = False
            self.isy.connection_events.notify(ES_DISCONNECTED)

    def subscribe(self):
        """Subscribe to the Event Stream."""
        if not self._subscribed and self._connected:
            if ATTR_STREAM_ID not in self.data:
                msg = self._create_message(strings.SUB_MSG)
                self.write(msg)
            else:
                msg = self._create_message(strings.RESUB_MSG)
                self.write(msg)
            self._subscribed = True

    def unsubscribe(self):
        """Unsubscribe from the Event Stream."""
        if self._subscribed and self._connected:
            msg = self._create_message(strings.UNSUB_MSG)
            self.write(msg)
            self._subscribed = False
            self.disconnect()

    @property
    def connected(self):
        """Return if the module is connected to the ISY or not."""
        return self._connected

    @property
    def heartbeat_time(self):
        """Return the last ISY Heartbeat time."""
        if self._lasthb is not None:
            return (now() - self._lasthb).seconds
        return 0.0

    def _lost_connection(self, delay=0):
        """React when the event stream connection is lost."""
        self.disconnect()
        _LOGGER.warning("PyISY lost connection to the ISY event stream.")
        self.isy.connection_events.notify(ES_LOST_STREAM_CONNECTION)
        if self._on_lost_function is not None:
            time.sleep(delay)
            self._on_lost_function()

    def watch(self):
        """Watch the subscription connection and report if dead."""
        if not self._subscribed:
            _LOGGER.debug("PyISY watch called without a subscription.")
            return

        event_reader = ISYEventReader(self.socket)

        while self._running and self._subscribed:
            # verify connection is still alive
            if self.heartbeat_time > self._hbwait:
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
                    self._route_message(message)
                except Exception as ex:  # pylint: disable=broad-except
                    _LOGGER.warning(
                        "PyISY encountered while routing message '%s': %s", message, ex
                    )

    def __del__(self):
        """Ensure we unsubscribe on destroy."""
        self.unsubscribe()


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
        if not len(_LOGGER.handlers):
            logging.basicConfig(
                format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT, level=LOG_LEVEL
            )
            _LOGGER.addHandler(logging.NullHandler())

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
        self._sid = None
        self._program_key = None
        self.websocket_task = None

        if websession is None:
            websession = get_new_client_session(use_https, tls_ver)

        self.req_session = websession
        self.sslcontext = get_sslcontext(use_https, tls_ver)
        self._loop = asyncio.get_running_loop()

        self._url = "wss://" if self.use_https else "ws://"
        self._url += f"{self._address}:{self._port}{self._webroot}/rest/subscribe"

    def start(self):
        """Start the websocket connection."""
        if self.status != ES_CONNECTED:
            _LOGGER.info("Starting websocket connection.")
            self.status = ES_INITIALIZING
            self.websocket_task = self._loop.create_task(self.websocket())

    def stop(self):
        """Close websocket connection."""
        self.status = ES_STOP_UPDATES
        if self.websocket_task is not None and not self.websocket_task.done():
            self.websocket_task.cancel()

    async def reconnect(self, delay=RECONNECT_DELAY, retries=0):
        """Reconnect to a disconnected websocket."""
        if self.status == ES_CONNECTED:
            return
        if self.websocket_task is not None and not self.websocket_task.done():
            self.websocket_task.cancel()
        self.status = ES_RECONNECTING
        _LOGGER.info("PyISY attempting stream reconnect in %ss.", delay)
        await asyncio.sleep(delay)
        retries = (retries + 1) if retries < WS_MAX_RETRIES else WS_MAX_RETRIES
        self.websocket_task = self._loop.create_task(self.websocket(retries))

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

    async def _route_message(self, msg):
        """Route a received message from the event stream."""
        # check xml formatting
        try:
            xmldoc = minidom.parseString(msg)
        except xml.parsers.expat.ExpatError:
            _LOGGER.warning("ISY Received Malformed XML:\n" + msg)
            return
        _LOGGER.log(LOG_VERBOSE, "ISY Update Received:\n" + msg)

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

    def update_received(self, xmldoc):
        """Set the socket ID."""
        self._sid = attr_from_xml(xmldoc, "Event", ATTR_STREAM_ID)
        _LOGGER.debug("ISY Updated Events Stream ID")

    async def websocket(self, retries=0):
        """Start websocket connection."""
        try:
            async with self.req_session.ws_connect(
                self._url,
                auth=self._auth,
                heartbeat=WS_HEARTBEAT,
                headers=WS_HEADERS,
                timeout=WS_TIMEOUT,
                ssl=self.sslcontext,
            ) as ws:
                self.status = ES_CONNECTED
                retries = 0
                _LOGGER.debug("Successfully connected to websocket... %s", self.status)

                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        await self._route_message(msg.data)

                    elif msg.type == aiohttp.WSMsgType.CLOSED:
                        _LOGGER.warning("Websocket connection closed: %s", msg.data)
                        await ws.close()
                        break

                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        _LOGGER.error("Websocket error: %s", ws.exception())
                        break

                    elif msg.type == aiohttp.WSMsgType.PING:
                        _LOGGER.debug("Websocket ping received.")
                        ws.pong()

                    elif msg.type == aiohttp.WSMsgType.PONG:
                        _LOGGER.debug("Websocket pong received.")

                    elif msg.type == aiohttp.WSMsgType.BINARY:
                        _LOGGER.warning("Unexpected binary message received.")

            self.status = ES_DISCONNECTED

        except (
            aiohttp.ClientOSError,
            aiohttp.client_exceptions.ServerDisconnectedError,
        ):
            _LOGGER.debug("ISY not ready or closed connection. Retrying.")
            await self.reconnect(WS_RETRY_BACKOFF[retries], retries=retries)
        except aiohttp.ClientConnectorError:
            if self.status != ES_STOP_UPDATES:
                _LOGGER.error("Websocket Client Connector Error.")
                self.status = ES_LOST_STREAM_CONNECTION
                await self.reconnect(RECONNECT_DELAY)
        except asyncio.CancelledError:
            self.status = ES_DISCONNECTED
        except Exception as err:
            if self.status != ES_STOP_UPDATES:
                _LOGGER.exception("Unexpected error %s", err)
                self.status = ES_LOST_STREAM_CONNECTION
                await self.reconnect(RECONNECT_DELAY)
        else:
            if self.status != ES_STOP_UPDATES:
                self.status = ES_DISCONNECTED
                await self.reconnect(RECONNECT_DELAY)
