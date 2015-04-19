from .Connection import Connection
from .configuration import configuration
from .Nodes import Nodes
from .Programs import Programs
from .Events import EventStream
from .Variables import Variables
from .Climate import Climate
# from .networking import networking
import logging
from threading import Thread


class ISY(object):

    """
    ISY class

    DESCRIPTION:
        This is the main class that handles interaction with
        the ISY device.

    ATTRIBUTES:
        x10_commands: dictionary of the commands that can be
                      sent to X10 devices.
        auto_update: boolean that controls whether the children
                     update threads should be running.
            True: start update threads
            False: stop update threads
        conn: ISY HTTP connection
        configuration: ISY Configuration details
        nodes: ISY Nodes (scenes and devices)
        programs: ISY programs
        variables: ISY variables
        climate: ISY climate information (only if installed on device)
        networking: ISY networking commands (only if installed on device)
    """

    x10_commands = {
        'all_off': 1,
        'all_on': 4,
        'on': 3,
        'off': 11,
        'bright': 7,
        'dim': 15
    }

    def __init__(self, address, port, username, password,
                 use_https=False, log=None):
        """
        Initiates the ISY class.

        address: String of the IP address of the ISY device
        port: String of the port over which the ISY is serving its API
        username: String of the administrator username for the ISY
        password: String of the administrator password for the ISY
        use_https: [optional] Boolean of whether secured HTTP should be used
        log: [optional] Log file class from logging module
        """
        if log is None:
            self.log = logging.getLogger(__name__)
        else:
            self.log = log

        try:
            self.conn = Connection(self, address, port, username,
                                   password, use_https)

        except ValueError as e:
            self._connected = False
            try:
                self.log.error(e.message)
            except AttributeError:
                self.log.error(e.args[0])

        else:
            self._connected = True
            self.configuration = configuration(self,
                                               xml=self.conn.getConfiguration())
            self.nodes = Nodes(self, xml=self.conn.getNodes())
            self.programs = Programs(self, xml=self.conn.getPrograms())
            self.variables = Variables(self, xml=self.conn.getVariables())
            self._events = None  # create this JIT so no socket reuse
            self.auto_reconnect = True
            self._reconnect_thread = None

            if self.configuration['Weather Information']:
                self.climate = Climate(self, xml=self.conn.getClimate())
            else:
                self.climate = None
            # if self.configuration['Networking Module']:
            #     self.networking = networking(self, xml=self.conn.getNetwork())

    def __del__(self):
        # not the best method, I know, but this "forces" Python to clean up
        # the subscription sockets if it isn't done explicitly by the user.
        # As a rule of thumb, this should not be relied upon. The subscription
        # should be closed explicitly by the program.
        # See: Zen of Python Line 2
        self.auto_update = False

    @property
    def connected(self):
        return self._connected

    @property
    def auto_update(self):
        if self._events is not None:
            return self._events.running
        else:
            return False

    @auto_update.setter
    def auto_update(self, val):
        if val and not self.auto_update:
            # create new event stream socket
            self._events = EventStream(self, self.on_lost_event_stream)
        self._events.running = val

    def on_lost_event_stream(self):
        del(self._events)
        self._events = None

        if self.auto_reconnect and self._reconnect_thread is None:
            # attempt to reconnect
            self._reconnect_thread = Thread(target=self.auto_reconnecter)
            self._reconnect_thread.daemon = True
            self._reconnect_thread.start()

    def auto_reconnecter(self):
        while self.auto_reconnect and not self.auto_update:
            self.log.warning('PyISY attempting stream reconnect.')
            del(self._events)
            self._events = EventStream(self, self.on_lost_event_stream)
            self._events.running = True

        if not self.auto_update:
            del(self._events)
            self._events = None
            self.log.warning('PyISY could not reconnect to the event stream.')
        else:
            self.log.warning('PyISY reconnected to the event stream.')

        self._reconnect_thread = None

    def sendX10(self, address, cmd):
        """
        Sends an X10 command.

        address: String of X10 device address (Ex: A10)
        cmd: String of command to execute. Any key of x10_commands can be used
        """
        if cmd in self.x10_commands:
            command = self.x10_commands[cmd]
            result = self.sendX10(address, command)
            if result is not None:
                self.log.info('ISY Sent X10 Command: ' +
                              cmd + ' To: ' + address)
            else:
                self.log.error('ISY Failed to send X10 Command: '
                               + cmd + ' To: ' + address)
