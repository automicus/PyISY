from Connection import Connection
from configuration import configuration
from Nodes import Nodes
from Programs import Programs
from Events import EventStream
from Variables import Variables
from Climate import Climate
#from networking import networking


class DummyLog(object):
    """
    DummyLog class

    Template for log file class.
    """
    def __init__(self, *args, **kwargs):
        pass

    def write(self, msg):
        print msg
    info = write
    warning = write
    error = write
    critical = write
    continuation = write


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
        log: [optional] Log file class, template in this Module
        """
        if log is None:
            self.log = DummyLog()
        else:
            self.log = log

        self.conn = Connection(self, address, port, username,
                               password, use_https)
        self.configuration = configuration(self,
                                           xml=self.conn.getConfiguration())
        self.nodes = Nodes(self, xml=self.conn.getNodes())
        self.programs = Programs(self, xml=self.conn.getPrograms())
        self.variables = Variables(self, xml=self.conn.getVariables())
        self._events = EventStream(self)

        if len(self.configuration) == 0:
            self.log.error('ISY Unable to connect.')
        else:
            if self.configuration['Weather Information']:
                self.climate = Climate(self, xml=self.conn.getClimate())
        #    if self.configuration['Networking Module']:
        #        self.networking = networking(self, xml=self.conn.getNetwork())

    def isAlive(self):
        """Indicates if the update thread is running."""
        for thread in self._threads:
            return thread.isAlive()
        return self._events.running

    def stop(self):
        """Stops auto updating."""
        self.auto_update = False

    @property
    def auto_update(self):
        return self._events.running

    @auto_update.setter
    def auto_update(self, val):
        self._events.running = val

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
