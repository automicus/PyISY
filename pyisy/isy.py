"""Module for connecting to and interacting with the ISY."""

from __future__ import annotations

import asyncio
from threading import Thread
from xml.dom import minidom

import aiohttp

from .clock import Clock
from .configuration import Configuration
from .connection import Connection, TLSVer
from .constants import (
    ATTR_ACTION,
    CMD_X10,
    CONFIG_NETWORKING,
    CONFIG_PORTAL,
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
from .events.tcpsocket import EventStream
from .events.websocket import WebSocketClient
from .exceptions import ISYResponseParseError
from .helpers import EventEmitter, value_from_xml
from .logging import _LOGGER, enable_logging
from .networking import NetworkResources
from .node_servers import NodeServers
from .nodes import Nodes
from .programs import Programs
from .variables import Variables


class ISY:
    """
    This is the main class that handles interaction with the ISY device.

    |  address: String of the IP address of the ISY device
    |  port: String of the port over which the ISY is serving its API
    |  username: String of the administrator username for the ISY
    |  password: String of the administrator password for the ISY
    |  use_https: [optional] Boolean of whether secured HTTP should be used
    |  tls_ver: [optional, deprecated] TLS version to use. Defaults to "auto",
       which lets OpenSSL negotiate the highest version both peers support
       (floor: TLS 1.2). Stock ISY-994 firmware (4.5.4+) defaults to TLS 1.2
       and current eisy/Polisy IoX firmware supports TLS 1.2 + 1.3, so "auto"
       works for all unmodified controllers. Passing a numeric value (1.1,
       1.2, 1.3) still works but emits a DeprecationWarning; pin only when
       needed (e.g. an ISY-994 manually downgraded to TLS 1.0/1.1).
    |  verify_ssl: [optional] If True, validate the controller's certificate
       and hostname. Defaults to False because eisy/Polisy/ISY-994 ship
       self-signed certs out of the box. Set True only when you have
       installed a properly-signed certificate on the controller.

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

    def __init__(
        self,
        address: str,
        port: int,
        username: str,
        password: str,
        use_https: bool = False,
        tls_ver: TLSVer = "auto",
        webroot: str = "",
        websession: aiohttp.ClientSession | None = None,
        use_websocket: bool = False,
        verify_ssl: bool = False,
    ) -> None:
        """Initialize the primary ISY Class."""
        self._events: EventStream | None = None  # create this JIT so no socket reuse
        self._reconnect_thread = None
        self._connected: bool = False

        if len(_LOGGER.handlers) == 0:
            enable_logging(add_null_handler=True)

        self.conn = Connection(
            address=address,
            port=port,
            username=username,
            password=password,
            use_https=use_https,
            tls_ver=tls_ver,
            webroot=webroot,
            websession=websession,
            verify_ssl=verify_ssl,
        )

        self.websocket: WebSocketClient | None = None
        if use_websocket:
            self.websocket = WebSocketClient(
                isy=self,
                address=address,
                port=port,
                username=username,
                password=password,
                use_https=use_https,
                tls_ver=tls_ver,
                webroot=webroot,
                websession=websession,
                verify_ssl=verify_ssl,
            )

        self.configuration: Configuration | None = None
        self.clock: Clock | None = None
        self.nodes: Nodes | None = None
        self.node_servers: NodeServers | None = None
        self.programs: Programs | None = None
        self.variables: Variables | None = None
        self.networking: NetworkResources | None = None
        self._hostname = address
        self.connection_events = EventEmitter()
        self.status_events = EventEmitter()
        self.system_status = SYSTEM_BUSY
        self.loop = asyncio.get_running_loop()
        self._uuid: str | None = None

    async def initialize(self, with_node_servers=False):
        """Initialize the connection with the ISY."""
        config_xml = await self.conn.test_connection()
        self.configuration = Configuration(xml=config_xml)
        self._uuid = self.configuration["uuid"]
        if not self.configuration["model"].startswith("ISY 994"):
            self.conn.increase_available_connections()

        load_network = bool(self.configuration[CONFIG_NETWORKING] or self.configuration.get(CONFIG_PORTAL))
        async with asyncio.TaskGroup() as tg:
            status_task = tg.create_task(self.conn.get_status())
            time_task = tg.create_task(self.conn.get_time())
            nodes_task = tg.create_task(self.conn.get_nodes())
            programs_task = tg.create_task(self.conn.get_programs())
            var_defs_task = tg.create_task(self.conn.get_variable_defs())
            vars_task = tg.create_task(self.conn.get_variables())
            network_task = tg.create_task(self.conn.get_network()) if load_network else None

        status_xml = status_task.result()
        time_xml = time_task.result()
        nodes_xml = nodes_task.result()
        programs_xml = programs_task.result()

        # Fail fast if the controller didn't return any of the load-bearing
        # responses — most often because the ISY is still booting. Mounting
        # empty managers silently leads to confused downstream consumers.
        if any(x is None for x in (status_xml, time_xml, nodes_xml, programs_xml)):
            raise ISYResponseParseError(
                "ISY did not return all setup data; the controller may still be initializing."
            )

        self.clock = Clock(self, xml=time_xml)
        self.nodes = Nodes(self, xml=nodes_xml)
        self.programs = Programs(self, xml=programs_xml)
        self.variables = Variables(
            self,
            def_xml=var_defs_task.result(),
            var_xml=vars_task.result(),
        )
        if network_task is not None:
            self.networking = NetworkResources(self, xml=network_task.result())
        await self.nodes.update(xml=status_xml)
        if self.node_servers and with_node_servers:
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
    def conf(self) -> Configuration:
        """Return the status of the connection (shortcut property)."""
        return self.configuration

    @property
    def connected(self) -> bool:
        """Return the status of the connection."""
        return self._connected

    @property
    def auto_update(self) -> bool:
        """Return the auto_update property."""
        if self.websocket is not None:
            return self.websocket.status == ES_CONNECTED
        if self._events is not None:
            return self._events.running
        return False

    @auto_update.setter
    def auto_update(self, val: bool) -> None:
        """Set the auto_update property."""
        if self.websocket is not None:
            _LOGGER.warning("Websockets are enabled. Use isy.websocket.start() or .stop() instead.")
            return
        if val and not self.auto_update:
            # create new event stream socket
            self._events = EventStream(self, self.conn.connection_info, self._on_lost_event_stream)
        if self._events is not None:
            self.connection_events.notify(ES_START_UPDATES if val else ES_STOP_UPDATES)
            self._events.running = val

    @property
    def hostname(self) -> str:
        """Return the hostname."""
        return self._hostname

    @property
    def protocol(self) -> str:
        """Return the protocol for this entity."""
        return PROTO_ISY

    @property
    def uuid(self) -> str:
        """Return the ISY's uuid."""
        return self._uuid

    def _on_lost_event_stream(self) -> None:
        """Handle lost connection to event stream."""
        del self._events
        self._events = None

        if self.auto_reconnect and self._reconnect_thread is None:
            # attempt to reconnect
            self._reconnect_thread = Thread(target=self._auto_reconnecter)
            self._reconnect_thread.daemon = True
            self._reconnect_thread.start()

    def _auto_reconnecter(self) -> None:
        """Auto-reconnect to the event stream."""
        while self.auto_reconnect and not self.auto_update:
            _LOGGER.warning("PyISY attempting stream reconnect.")
            del self._events
            self._events = EventStream(self, self.conn.connection_info, self._on_lost_event_stream)
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
        if not await self.conn.request(req_url, retry404=True):
            _LOGGER.warning("Error performing query.")
            return False
        _LOGGER.debug("ISY Query requested successfully.")
        return True

    async def send_x10_cmd(self, address: str, cmd: str) -> None:
        """
        Send an X10 command.

        address: String of X10 device address (Ex: A10)
        cmd: String of command to execute. Any key of x10_commands can be used
        """
        if cmd in X10_COMMANDS:
            command = X10_COMMANDS.get(cmd)
            req_url = self.conn.compile_url([CMD_X10, address, str(command)])
            result = await self.conn.request(req_url, retry404=True)
            if result is not None:
                _LOGGER.info("ISY Sent X10 Command: %s To: %s", cmd, address)
            else:
                _LOGGER.error("ISY Failed to send X10 Command: %s To: %s", cmd, address)

    def system_status_changed_received(self, xmldoc: minidom.Element) -> None:
        """Handle System Status events from an event stream message."""
        action = value_from_xml(xmldoc, ATTR_ACTION)
        if not action or action not in SYSTEM_STATUS:
            return
        self.system_status = action
        self.status_events.notify(action)
