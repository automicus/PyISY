"""ISY Event Stream."""
import datetime
import select
import socket
import ssl
import sys
import xml
from threading import Thread, ThreadError
from xml.dom import minidom

from . import strings
from .constants import (
    ATTR_ACTION,
    ATTR_CONTROL,
    ATTR_ID,
    ATTR_STREAM_ID,
    ATTR_VAR,
    POLL_TIME,
    PROP_STATUS,
    SOCKET_BUFFER_SIZE,
    TAG_NODE,
)
from .helpers import attr_from_xml, value_from_xml


class EventStream:
    """Class to represent the Event Stream from the ISY."""

    def __init__(self, isy, connection_info, on_lost_func=None):
        """Initializze the EventStream class."""
        self.isy = isy
        self._running = False
        self._writer = None
        self._thread = None
        self._subscribed = False
        self._connected = False
        self._lasthb = None
        self._hbwait = 0
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
                server_hostname="https://{}".format(self.data["addr"]),
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
            self.isy.log.warning("ISY Received Malformed XML:\n" + msg)
            return
        self.isy.log.debug("ISY Update Received:\n" + msg)

        # A wild stream id appears!
        if f"{ATTR_STREAM_ID}=" in msg and ATTR_STREAM_ID not in self.data:
            self.update_received(xmldoc)

        # direct the event message
        cntrl = value_from_xml(xmldoc, ATTR_CONTROL)
        if not cntrl:
            return
        if cntrl == "_0":  # ISY HEARTBEAT
            self._lasthb = datetime.datetime.now()
            self._hbwait = int(value_from_xml(xmldoc, ATTR_ACTION))
            self.isy.log.debug("ISY HEARTBEAT: %s", self._lasthb.isoformat())
        elif cntrl == PROP_STATUS:  # NODE UPDATE
            self.isy.nodes.update_received(xmldoc)
        elif cntrl[0] != "_":  # NODE CONTROL EVENT
            self.isy.nodes.control_message_received(xmldoc)
        elif cntrl == "_11":  # WEATHER UPDATE
            if self.isy.configuration["Weather Information"]:
                self.isy.climate.update_received(xmldoc)
        elif cntrl == "_1":  # Trigger Update
            if f"<{ATTR_VAR}" in msg:  # VARIABLE
                self.isy.variables.update_received(xmldoc)
            elif f"<{ATTR_ID}>" in msg:  # PROGRAM
                self.isy.programs.update_received(xmldoc)
            elif f"<{TAG_NODE}>" in msg and "[" in msg:  # Node Server Update
                pass  # This is most likely a duplicate node update.
            else:  # SOMETHING HAPPENED WITH A PROGRAM FOLDER
                # but they ISY didn't tell us what, so...
                self.isy.programs.update()

    def update_received(self, xmldoc):
        """Set the socket ID."""
        self.data[ATTR_STREAM_ID] = attr_from_xml(xmldoc, "Event", ATTR_STREAM_ID)
        self.isy.log.debug("ISY Updated Events Stream ID")

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
            self.isy.log.info("ISY Starting Updates")
            if self.connect():
                self.subscribe()
                self._running = True
                self._thread = Thread(target=self.watch)
                self._thread.daemon = True
                self._thread.start()
        else:
            self.isy.log.info("ISY Stopping Updates")
            self._running = False
            self.unsubscribe()
            self.disconnect()

    def read(self):
        """Read data from the socket."""
        loop = True
        output = ""
        while loop:
            try:
                new_data = self.socket.recv(SOCKET_BUFFER_SIZE)
            except ssl.SSLWantReadError:
                pass
            except socket.error:
                loop = False
            else:
                if len(new_data) < SOCKET_BUFFER_SIZE:
                    loop = False
                if sys.version_info.major == 3:
                    new_data = new_data.decode("utf-8")
                output += new_data

        return output.split("\n")

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
                self.isy.log.error("PyISY could not connect to ISY event stream.")
                if self._on_lost_function is not None:
                    self._on_lost_function()
                return False
            self.socket.setblocking(0)
            self._writer = self.socket.makefile("w")
            self._connected = True
            return True
        return True

    def disconnect(self):
        """Disconnect from the Event Stream socket."""
        if self._connected:
            self.socket.close()
            self._connected = False
            self._subscribed = False
            self._running = False

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
        """Return if the module is connnected to the ISY or not."""
        return self._connected

    @property
    def heartbeat_time(self):
        """Return the last ISY Heartbeat time."""
        if self._lasthb is not None:
            return (datetime.datetime.now() - self._lasthb).seconds
        return 0.0

    def watch(self):
        """Watch the subscription connection and report if dead."""
        if self._subscribed:
            while self._running and self._subscribed:
                # verify connection is still alive
                if self.heartbeat_time > self._hbwait:
                    self.disconnect()
                    self.isy.log.warning(
                        "PyISY lost connection to the ISY event stream."
                    )
                    if self._on_lost_function is not None:
                        self._on_lost_function()

                # poll socket for new data
                inready, _, _ = select.select([self.socket], [], [], POLL_TIME)
                if self.socket in inready:
                    for data in self.read():
                        if data.startswith("<?xml"):
                            data = data.strip().replace("POST reuse HTTP/1.1", "")
                            self._route_message(data)
