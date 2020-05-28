"""ISY Event Stream."""
import asyncio
import logging
import socket
import ssl
from threading import Thread, ThreadError
import time
import xml
from xml.dom import minidom

from . import strings
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
    ES_LOADED,
    ES_LOST_STREAM_CONNECTION,
    LOG_VERBOSE,
    POLL_TIME,
    PROP_STATUS,
    RECONNECT_DELAY,
    TAG_EVENT_INFO,
    TAG_NODE,
)
from ..exceptions import ISYInvalidAuthError, ISYMaxConnections, ISYStreamDataError
from ..helpers import attr_from_xml, now, value_from_xml
from .eventreader import ISYEventReader

_LOGGER = logging.getLogger(__name__)  # Allows targeting pyisy.events in handlers.


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
        if self.data.get("tls"):
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
            except OSError as err:
                _LOGGER.exception(
                    "PyISY could not connect to ISY event stream. %s", err
                )
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
                    self._route_message(message)
                except Exception as ex:  # pylint: disable=broad-except
                    _LOGGER.warning(
                        "PyISY encountered while routing message '%s': %s", message, ex
                    )
                    raise

    def __del__(self):
        """Ensure we unsubscribe on destroy."""
        self.unsubscribe()
