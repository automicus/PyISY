from ..constants import _change2update_interval
from VarEvents import Property


class Folder(object):
    """
    Object representing a program folder on the ISY device.

    |  parent: The folder manager object.
    |  pid: The folder ID.
    |  pname: The folder name.
    |  pstatus: The current folder status.

    :ivar dtype: Returns the type of the object (folder).
    :ivar status: Watched property representing the current status of the
                  folder.
    """

    status = Property(0, readonly=True)
    dtype = 'folder'

    def __init__(self, parent, pid, pname, pstatus):
        self.noupdate = False
        self.parent = parent
        self.name = pname
        self._id = pid

        self.status.update(pstatus, force=True, silent=True)

    def __str__(self):
        """ Returns a string representation of the folder. """
        return 'Folder(' + self._id + ')'

    @property
    def leaf(self):
        return self

    def update(self, waitTime=0, data=None):
        """
        Updates the status of the program.

        |  data: [optional] The data to update the folder with.
        |  waitTime: [optional] Seconds to wait before updating.
        """
        if not self.noupdate:
            if data is not None:
                self.status.update(data['pstatus'], force=True, silent=True)
            else:
                self.parent.update(waitTime, pid=self._id)

    def run(self):
        """ Runs the appropriate clause of the object. """
        response = self.parent.parent.conn.programRun(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not run program: '
                                           + self._id)
            return False
        else:
            self.parent.parent.log.info('ISY ran program: ' + self._id)
            self.update(_change2update_interval)
            return True

    def runThen(self):
        """ Runs the THEN clause of the object. """
        response = self.parent.parent.conn.programRunThen(self._id)

        if response is None:
            self.parent.parent.log.warning("ISY couldn't run then in program: "
                                           + self._id)
            return False
        else:
            self.parent.parent.log.info('ISY ran then in program: ' + self._id)
            self.update(_change2update_interval)
            return True

    def runElse(self):
        """ Runs the ELSE clause of the object. """
        response = self.parent.parent.conn.programRunElse(self._id)

        if response is None:
            self.parent.parent.log.warning("ISY couldn't run else in program: "
                                           + self._id)
            return False
        else:
            self.parent.parent.log.info('ISY ran else in program: ' + self._id)
            self.update(_change2update_interval)
            return True

    def stop(self):
        """ Stops the object if it is running. """
        response = self.parent.parent.conn.programStop(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not stop program: '
                                           + self._id)
            return False
        else:
            self.parent.parent.log.info('ISY stopped program: ' + self._id)
            self.update(_change2update_interval)
            return True
