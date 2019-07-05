"""ISY Program Folders."""
from VarEvents import Property

from ..constants import ATTR_FOLDER, UPDATE_INTERVAL


class Folder:
    """
    Object representing a program folder on the ISY device.

    |  programs: The folder manager object.
    |  pid: The folder ID.
    |  pname: The folder name.
    |  pstatus: The current folder status.

    :ivar dtype: Returns the type of the object (folder).
    :ivar status: Watched property representing the current status of the
                  folder.
    """

    status = Property(0, readonly=True)
    dtype = ATTR_FOLDER

    def __init__(self, programs, pid, pname, pstatus):
        """Intialize the Folder class."""
        self.noupdate = False
        self._programs = programs
        self.isy = programs.isy
        self.name = pname
        self._id = pid
        self.status.update(pstatus, force=True, silent=True)

    def __str__(self):
        """Return a string representation of the node."""
        return '{}({})'.format(type(self).__name__, self._id)

    @property
    def nid(self):
        """Return the program or folder ID."""
        return self._id

    @property
    def leaf(self):
        """Get the leaf property."""
        return self

    def update(self, wait_time=0, data=None):
        """
        Update the status of the program.

        |  data: [optional] The data to update the folder with.
        |  wait_time: [optional] Seconds to wait before updating.
        """
        if not self.noupdate:
            if data is not None:
                self.status.update(data['pstatus'], force=True, silent=True)
            else:
                self._programs.update(wait_time, pid=self._id)

    def send_pgrm_cmd(self, command):
        """Run the appropriate clause of the object."""
        req_url = self.isy.conn.compile_url(['programs', str(self._id),
                                             command])
        result = self.isy.conn.request(req_url)
        if not result:
            self.isy.log.warning('ISY could not run program: %s', self._id)
            return False
        self.isy.log.info('ISY ran program: ' + self._id)
        self.update(UPDATE_INTERVAL)
        return True
