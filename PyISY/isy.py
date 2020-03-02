"""Module for connecting to and interacting with the ISY."""
import logging
from threading import Thread

from .climate import Climate
from .configuration import Configuration
from .connection import Connection
from .constants import COMMAND_FRIENDLY_NAME, UOM_TO_STATES, X10_COMMANDS
from .events import EventStream
from .Nodes import Nodes
from .Nodes.node import Node
from .Programs import Programs
from .Programs.folder import Folder
from .Programs.program import Program
from .Variables import Variables


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
    |  log: [optional] Log file class from logging module

    :ivar auto_reconnect: Boolean value that indicates if the class should
                          auto-reconnect to the event stream if the connection
                          is lost.
    :ivar auto_update: Boolean value that controls the class's subscription to
                       the event stream that allows node, program, and climate
                       values to be updated automatically.
    :ivar climate: Climate manager that holds all climate properties from the
                   controller if the climate module is installed on the
                   controller.
    :ivar connected: Read only boolean value indicating if the class is
                     connected to the controller.
    :ivar log: Logger used by the class and its children.
    :ivar nodes: :class:`~PyISY.Nodes.Nodes` manager that interacts with
                 Insteon nodes and groups.
    :ivar programs: Program manager that interacts with ISY programs and i
                    folders.
    :ivar variables: Variable manager that interacts with ISY variables.
    """

    auto_reconnect = True

    def __init__(
        self, address, port, username, password, use_https=False, tls_ver=1.1, log=None
    ):
        """Initialize the primary ISY Class."""
        self._events = None  # create this JIT so no socket reuse
        self._reconnect_thread = None

        if log is None:
            self.log = logging.getLogger(__name__)
            self.log.addHandler(NullHandler())
        else:
            self.log = log

        try:
            self.conn = Connection(
                self, address, port, username, password, use_https, tls_ver
            )
        except ValueError as err:
            self._connected = False
            try:
                self.log.error(err.message)
            except AttributeError:
                self.log.error(err.args[0])

        else:
            self._connected = True
            self.configuration = Configuration(self, xml=self.conn.get_config())
            self._add_commands()
            self.nodes = Nodes(self, xml=self.conn.get_nodes())
            self.programs = Programs(self, xml=self.conn.get_programs())
            self.variables = Variables(
                self,
                def_xml=self.conn.get_variable_defs(),
                var_xml=self.conn.get_variables(),
            )

            if self.configuration.get("Weather Information"):
                self.climate = Climate(self, xml=self.conn.get_climate())
            else:
                self.climate = None
            # if self.configuration['Networking Module']:
            #     self.networking = NetworkResources(self,
            #       xml=self.conn.get_network())

    def __del__(self):
        """Turn off auto updating when the class is deleted."""
        # not the best method, I know, but this "forces" Python to clean up
        # the subscription sockets if it isn't done explicitly by the user.
        # As a rule of thumb, this should not be relied upon. The subscription
        # should be closed explicitly by the program.
        # See: Zen of Python Line 2
        self.auto_update = False

    @property
    def connected(self):
        """Return the status of the connection."""
        return self._connected

    @property
    def auto_update(self):
        """Return the auto_update property."""
        if self._events is not None:
            return self._events.running
        return False

    @auto_update.setter
    def auto_update(self, val):
        """Set the auto_update property."""
        if val and not self.auto_update:
            # create new event stream socket
            self._events = EventStream(
                self, self.conn.connection_info, self._on_lost_event_stream
            )
        if self._events is not None:
            self._events.running = val

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
            self.log.warning("PyISY attempting stream reconnect.")
            del self._events
            self._events = EventStream(
                self, self.conn.connection_info, self._on_lost_event_stream
            )
            self._events.running = True

        if not self.auto_update:
            del self._events
            self._events = None
            self.log.warning("PyISY could not reconnect to the event stream.")
        else:
            self.log.warning("PyISY reconnected to the event stream.")

        self._reconnect_thread = None

    @staticmethod
    def _add_node_command(cmd_name, command, value=None):
        doc = "Send {} command to ISY".format(command)
        if value is None:

            def cmd(self, val=None):
                return self.send_cmd(command, val)

        else:

            def cmd(self):
                return self.send_cmd(command, value)

            doc = "{} with value {}".format(doc, value)

        cmd.__name__ = cmd_name
        cmd.__doc__ = doc
        setattr(Node, cmd_name, cmd)

    @staticmethod
    def _add_pgrm_command(command, cls):
        doc = "Send program {} command to ISY".format(command)

        def cmd(self):
            return self.send_pgrm_cmd(command)

        cmd.__name__ = command
        cmd.__doc__ = doc
        setattr(cls, command, cmd)

    def _add_commands(self):
        """
        Dynamically add functions for the commands listed.

        The function names are translated according to COMMAND_FRIENDLY_NAME
        in the constants file (e.g. DOF will be available at self.off())

        Any tuple of a command and a UOM value will add all possible commands
        from the UOM list in constants.

        FUTURE: Only add the commands needed depending on Node type.

        NOTE: `on` and climate setpoints are special and are still defined
        explicitly in the Node class.
        """
        commands = [
            ("DFON", None),
            ("DFOF", None),
            ("BRT", None),
            ("DIM", None),
            ("BEEP", None),
            ("SECMD", "84"),
            ("CLIMD", "98"),
            ("CLIFS", "99"),
        ]
        cmd_names = []
        for command, values in commands:
            cmd_name = COMMAND_FRIENDLY_NAME.get(command)
            self._add_node_command(cmd_name, command)
            cmd_names.append(cmd_name)
            if values:
                for val, cmd in UOM_TO_STATES[values].items():
                    cmd_val_name = "{}_{}".format(cmd_name, cmd.replace(" ", "_"))
                    self._add_node_command(cmd_val_name, command, val)
                    cmd_names.append(cmd_val_name)
        self.log.debug("ISY Added Node commands: %s", cmd_names)

        folder_commands = ["run", "runThen", "runElse", "stop", "enable", "disable"]
        for command in folder_commands:
            self._add_pgrm_command(command, Folder)
        self.log.debug("ISY Added Program/Folder commands: %s", folder_commands)

        prgm_commands = ["enableRunAtStartup", "disableRunAtStartup"]
        for command in folder_commands:
            self._add_pgrm_command(command, Program)
        self.log.debug("ISY Added Program commands: %s", prgm_commands)

    def sendX10(self, address, cmd):
        """
        Send an X10 command.

        address: String of X10 device address (Ex: A10)
        cmd: String of command to execute. Any key of x10_commands can be used
        """
        if cmd in X10_COMMANDS:
            command = X10_COMMANDS.get(cmd)
            req_url = self.conn.compile_url(["X10", address, str(command)])
            result = self.conn.request(req_url)
            if result is not None:
                self.log.info("ISY Sent X10 Command: %s To: %s", cmd, address)
            else:
                self.log.error(
                    "ISY Failed to send X10 Command: %s To: %s", cmd, address
                )


class NullHandler(logging.Handler):
    """NullHandler Logging Class Override."""

    def emit(self, record):
        """Override the Emit function."""
        pass
