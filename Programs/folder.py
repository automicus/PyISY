from ..constants import _change2update_interval
from VarEvents import Property


class Folder(object):

    status = Property(0, readonly=True)

    def __init__(self, parent, pid, pname, pstatus):
        self.noupdate = False
        self.parent = parent
        self.name = pname
        self._id = pid

        self.status.update(pstatus, force=True, silent=True)

    def __str__(self):
        return 'Folder(' + self._id + ')'

    def update(self, waitTime=0, data=None):
        if not self.noupdate:
            if data is not None:
                self.status.update(data['pstatus'], force=True, silent=True)
            else:
                self.parent.update(waitTime, pid=self._id)

    def run(self):
        response = self.parent.parent.conn.programRun(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not run program: '
                                           + self._id)
        else:
            self.parent.parent.log.info('ISY ran program: ' + self._id)
            self.update(_change2update_interval)

    def runThen(self):
        response = self.parent.parent.conn.programRunThen(self._id)

        if response is None:
            self.parent.parent.log.warning("ISY couldn't run then in program: "
                                           + self._id)
        else:
            self.parent.parent.log.info('ISY ran then in program: ' + self._id)
            self.update(_change2update_interval)

    def runElse(self):
        response = self.parent.parent.conn.programRunElse(self._id)

        if response is None:
            self.parent.parent.log.warning("ISY couldn't run else in program: "
                                           + self._id)
        else:
            self.parent.parent.log.info('ISY ran else in program: ' + self._id)
            self.update(_change2update_interval)

    def stop(self):
        response = self.parent.parent.conn.programStop(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not stop program: '
                                           + self._id)
        else:
            self.parent.parent.log.info('ISY stopped program: ' + self._id)
            self.update(_change2update_interval)
