"""ISY Program Folders."""
from ..constants import (
    CMD_DISABLE,
    CMD_ENABLE,
    CMD_RUN,
    CMD_RUN_ELSE,
    CMD_RUN_THEN,
    CMD_STOP,
    PROTO_FOLDER,
    TAG_FOLDER,
    UPDATE_INTERVAL,
    URL_PROGRAMS,
)
from ..helpers import EventEmitter


class Folder:
    """
    Object representing a program folder on the ISY device.

    |  programs: The folder manager object.
    |  address: The folder ID.
    |  pname: The folder name.
    |  pstatus: The current folder status.

    :ivar dtype: Returns the type of the object (folder).
    :ivar status: Watched property representing the current status of the
                  folder.
    """

    dtype = TAG_FOLDER

    def __init__(self, programs, address, pname, pstatus):
        """Initialize the Folder class."""
        self._id = address
        self._name = pname
        self._programs = programs
        self._status = pstatus
        self.isy = programs.isy
        self.status_events = EventEmitter()

    def __str__(self):
        """Return a string representation of the node."""
        return f"{type(self).__name__}({self._id})"

    @property
    def address(self):
        """Return the program or folder ID."""
        return self._id

    @property
    def leaf(self):
        """Get the leaf property."""
        return self

    @property
    def name(self):
        """Return the name of the Node."""
        return self._name

    @property
    def protocol(self):
        """Return the protocol for this entity."""
        return PROTO_FOLDER

    @property
    def status(self):
        """Return the current node state."""
        return self._status

    @status.setter
    def status(self, value):
        """Set the current node state and notify listeners."""
        if self._status != value:
            self._status = value
            self.status_events.notify(self._status)
        return self._status

    def update(self, wait_time=UPDATE_INTERVAL, data=None):
        """
        Update the status of the program.

        |  data: [optional] The data to update the folder with.
        |  wait_time: [optional] Seconds to wait before updating.
        """
        if data is not None:
            self.status = data["pstatus"]
            return
        self._programs.update(wait_time=wait_time, address=self._id)

    def send_cmd(self, command):
        """Run the appropriate clause of the object."""
        req_url = self.isy.conn.compile_url([URL_PROGRAMS, str(self._id), command])
        result = self.isy.conn.request(req_url)
        if not result:
            self.isy.log.warning(
                'ISY could not call "%s" on program: %s', command, self._id
            )
            return False
        self.isy.log.debug('ISY ran "%s" on program: %s', command, self._id)
        if not self.isy.auto_update:
            self.update()
        return True

    def enable(self):
        """Send command to the program/folder to enable it."""
        return self.send_cmd(CMD_ENABLE)

    def disable(self):
        """Send command to the program/folder to enable it."""
        return self.send_cmd(CMD_DISABLE)

    def run(self):
        """Send a run command to the program/folder."""
        return self.send_cmd(CMD_RUN)

    def run_then(self):
        """Send a runThen command to the program/folder."""
        return self.send_cmd(CMD_RUN_THEN)

    def run_else(self):
        """Send a runElse command to the program/folder."""
        return self.send_cmd(CMD_RUN_ELSE)

    def stop(self):
        """Send a stop command to the program/folder."""
        return self.send_cmd(CMD_STOP)
