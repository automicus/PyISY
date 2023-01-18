"""Module for connecting to and interacting with the ISY."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from threading import Thread
from typing import Any

from pyisy.clock import Clock
from pyisy.configuration import ConfigurationData
from pyisy.connection import Connection, ISYConnectionInfo
from pyisy.constants import (
    ATTR_ACTION,
    CMD_X10,
    ES_CONNECTED,
    ES_RECONNECT_FAILED,
    ES_RECONNECTING,
    ES_START_UPDATES,
    ES_STOP_UPDATES,
    PROTO_ISY,
    SYSTEM_BUSY,
    SYSTEM_STATUS,
    URL_QUERY,
    X10_COMMANDS,
)
from pyisy.events.tcpsocket import EventStream
from pyisy.events.websocket import WebSocketClient
from pyisy.helpers import value_from_xml
from pyisy.helpers.events import EventEmitter
from pyisy.logging import _LOGGER, enable_logging
from pyisy.networking import NetworkResources
from pyisy.node_servers import NodeServers
from pyisy.nodes import Nodes
from pyisy.programs import Programs
from pyisy.variables import Variables


class ISY:
    """
    This is the main class that handles interaction with the ISY device.

    |  address: String of the IP address of the ISY device
    |  port: String of the port over which the ISY is serving its API
    |  username: String of the administrator username for the ISY
    |  password: String of the administrator password for the ISY
    |  use_https: [optional] Boolean of whether secured HTTP should be used
    |  tls_ver: [optional] Number indicating the version of TLS encryption to
       use. Valid options are 1.1 or 1.2.

    :ivar auto_reconnect: Boolean value that indicates if the class should
                          auto-reconnect to the event stream if the connection
                          is lost.
    :ivar auto_update: Boolean value that controls the class's subscription to
                       the event stream that allows node, program
                       values to be updated automatically.
    :ivar connected: Read only boolean value indicating if the class is
                     connected to the controller.
    :ivar nodes: :class:`pyisy.nodes.Nodes` manager that interacts with
                 Insteon nodes and groups.
    :ivar programs: Program manager that interacts with ISY programs and i
                    folders.
    :ivar variables: Variable manager that interacts with ISY variables.
    """

    auto_reconnect = True
    clock: Clock
    conn: Connection
    connection_info: ISYConnectionInfo
    config: ConfigurationData | None = None
    nodes: Nodes | None = None
    node_servers: NodeServers | None = None
    programs: Programs
    variables: Variables
    networking: NetworkResources
    system_status: str = SYSTEM_BUSY
    websocket: WebSocketClient | None = None
    connection_events: EventEmitter
    status_events: EventEmitter
    loop: asyncio.AbstractEventLoop | None

    def __init__(
        self, connection_info: ISYConnectionInfo, use_websocket: bool = True
    ) -> None:
        """Initialize the primary ISY Class."""
        self._events = None  # create this JIT so no socket reuse
        self._reconnect_thread = None
        self._connected = False

        if len(_LOGGER.handlers) == 0:
            enable_logging(add_null_handler=True)

        # Initialize connection info and connection
        self.connection_info = connection_info
        self.conn = Connection(connection_info)

        # Setup websocket or fall back to TCP socket
        self.websocket = None
        if use_websocket:
            self.websocket = WebSocketClient(self, connection_info)

        # Initialize platforms
        self.clock = Clock(self)
        self.networking = NetworkResources(self)
        self.variables = Variables(self)
        self.programs = Programs(self)

        # Setup event emitters and loop
        self.connection_events = EventEmitter()
        self.status_events = EventEmitter()
        self.loop = asyncio.get_running_loop()

    async def initialize(
        self,
        nodes: bool = True,
        clock: bool = True,
        programs: bool = True,
        variables: bool = True,
        networking: bool = True,
        node_servers: bool = False,
    ) -> None:
        """Initialize the connection with the ISY."""
        self.config = await self.conn.test_connection()

        if self.config.platform == "IoX":
            self.conn.increase_available_connections()

        isy_setup_tasks: list[Awaitable[Any]] = []
        isy_setup_index: list[str] = []
        if nodes:
            isy_setup_tasks.append(self.conn.get_status())
            isy_setup_index.append(self.conn.get_status.__qualname__)
            isy_setup_tasks.append(self.conn.get_nodes())
            isy_setup_index.append(self.conn.get_nodes.__qualname__)

        if clock:
            isy_setup_tasks.append(self.clock.update())

        if programs:
            isy_setup_tasks.append(self.programs.update())

        if variables:
            isy_setup_tasks.append(self.variables.update())

        if networking and self.config.networking:
            isy_setup_tasks.append(self.networking.update())

        isy_setup_results = await asyncio.gather(*isy_setup_tasks)

        if nodes:
            self.nodes = Nodes(
                self,
                xml=isy_setup_results[isy_setup_index.index("Connection.get_nodes")],
            )
            await self.nodes.update(
                xml=isy_setup_results[isy_setup_index.index("Connection.get_status")]
            )  # Node Status

        if self.node_servers and node_servers:
            await self.node_servers.load_node_servers()

        self._connected = True

    async def shutdown(self) -> None:
        """Cleanup connections and prepare for exit."""
        if self.websocket is not None:
            self.websocket.stop()
        if self._events is not None and self._events.running:
            self.connection_events.notify(ES_STOP_UPDATES)
            self._events.running = False
        await self.conn.close()

    @property
    def conf(self):
        """Return the status of the connection.

        Left for backwards compatibility.
        """
        return self.config

    @property
    def connected(self):
        """Return the status of the connection."""
        return self._connected

    @property
    def auto_update(self):
        """Return the auto_update property."""
        if self.websocket is not None:
            return self.websocket.status == ES_CONNECTED
        if self._events is not None:
            return self._events.running
        return False

    @auto_update.setter
    def auto_update(self, val):
        """Set the auto_update property."""
        if self.websocket is not None:
            _LOGGER.warning(
                "Websockets are enabled. Use isy.websocket.start() or .stop() instead."
            )
            return
        if val and not self.auto_update:
            # create new event stream socket
            self._events = EventStream(
                self, self.conn.connection_info, self._on_lost_event_stream
            )
        if self._events is not None:
            self.connection_events.notify(ES_START_UPDATES if val else ES_STOP_UPDATES)
            self._events.running = val

    @property
    def hostname(self):
        """Return the hostname."""
        return self.connection_info.parsed_url.hostname

    @property
    def protocol(self):
        """Return the protocol for this entity."""
        return PROTO_ISY

    @property
    def uuid(self):
        """Return the ISY's uuid."""
        return self.config.uuid

    def _on_lost_event_stream(self):
        """Handle lost connection to event stream."""
        del self._events
        self._events = None

        if self.auto_reconnect and self._reconnect_thread is None:
            # attempt to reconnect
            self._reconnect_thread = Thread(target=self._auto_reconnecter)
            self._reconnect_thread.daemon = True
            self._reconnect_thread.start()

    def _auto_reconnecter(self):
        """Auto-reconnect to the event stream."""
        while self.auto_reconnect and not self.auto_update:
            _LOGGER.warning("PyISY attempting stream reconnect.")
            del self._events
            self._events = EventStream(
                self, self.conn.connection_info, self._on_lost_event_stream
            )
            self._events.running = True
            self.connection_events.notify(ES_RECONNECTING)

        if not self.auto_update:
            del self._events
            self._events = None
            _LOGGER.warning("PyISY could not reconnect to the event stream.")
            self.connection_events.notify(ES_RECONNECT_FAILED)
        else:
            _LOGGER.warning("PyISY reconnected to the event stream.")

        self._reconnect_thread = None

    async def query(self, address: str | None = None) -> bool:
        """Query all the nodes or a specific node if an address is provided .

        Args:
            address (string, optional): Node Address to query. Defaults to None.

        Returns:
            boolean: Returns `True` on successful command, `False` on error.
        """
        req_path = [URL_QUERY]
        if address is not None:
            req_path.append(address)
        req_url = self.conn.compile_url(req_path)
        if not await self.conn.request(req_url):
            _LOGGER.warning("Error performing query.")
            return False
        _LOGGER.debug("ISY Query requested successfully.")
        return True

    async def send_x10_cmd(self, address, cmd):
        """
        Send an X10 command.

        address: String of X10 device address (Ex: A10)
        cmd: String of command to execute. Any key of x10_commands can be used
        """
        if cmd in X10_COMMANDS:
            command = X10_COMMANDS.get(cmd)
            req_url = self.conn.compile_url([CMD_X10, address, str(command)])
            result = await self.conn.request(req_url)
            if result is not None:
                _LOGGER.info("ISY Sent X10 Command: %s To: %s", cmd, address)
            else:
                _LOGGER.error("ISY Failed to send X10 Command: %s To: %s", cmd, address)

    def system_status_changed_received(self, xmldoc):
        """Handle System Status events from an event stream message."""
        action = value_from_xml(xmldoc, ATTR_ACTION)
        if not action or action not in SYSTEM_STATUS:
            return
        self.system_status = action
        self.status_events.notify(action)
