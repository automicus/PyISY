from ..constants import _change2update_interval
from ..constants import _empty_time
from VarEvents import Property
from .folder import Folder


class Program(Folder):

    lastUpdate = Property(_empty_time, readonly=True)
    lastRun = Property(_empty_time, readonly=True)
    lastFinished = Property(_empty_time, readonly=True)
    enabled = Property(True)
    runAtStartup = Property(True)
    running = Property(False, readonly=True)
    ranThen = Property(0, readonly=True)
    ranElse = Property(0, readonly=True)

    def __init__(self, parent, pid, pstatus, plastup, plastrun, plastfin,
                 penabled, pstartrun, prunning):
        super(Program, self).__init__(parent, pid, pstatus)
        self.lastUpdate.update(plastup, force=True, silent=True)
        self.lastRun.update(plastrun, force=True, silent=True)
        self.lastFinished.update(plastfin, force=True, silent=True)
        self.enabled.update(penabled, force=True, silent=True)
        self.enabled.responder = self.__report_enabled__
        self.runAtStartup.update(pstartrun, force=True, silent=True)
        self.runAtStartup.responder = self.__report_startrun__
        self.running.update(prunning, force=True, silent=True)

    def __str__(self):
        return 'Program(' + self._id + ')'

    def __report_enabled__(self, val):
        self.noupdate = True
        fun = self.enable if val else self.disable
        fun()
        self.noupdate = False

    def __report_startrun__(self, val):
        self.noupdate = True
        fun = self.enableRunAtStartup if val else self.disableRunAtStartup
        fun()
        self.noupdate = False

    def update(self, waitTime=0, data=None):
        if not self.noupdate:
            if data is not None:
                prunning = (data['plastrun'] >= data['plastup']) or \
                    data['prunning']
                self.status.update(data['pstatus'], force=True, silent=True)
                self.lastUpdate.update(data['plastup'],
                                       force=True, silent=True)
                self.lastRun.update(data['plastrun'], force=True, silent=True)
                self.lastFinished.update(data['plastfin'],
                                         force=True, silent=True)
                self.enabled.update(data['penabled'], force=True, silent=True)
                self.runAtStartup.update(data['pstartrun'],
                                         force=True, silent=True)
                self.running.update(prunning, force=True, silent=True)
            else:
                self.parent.update(waitTime, pid=self._id)

    def enable(self):
        response = self.parent.parent.conn.programEnable(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not enable program: '
                                           + self._id)
        else:
            self.parent.parent.log.info('ISY enabled program: ' + self._id)
            self.update(_change2update_interval)

    def disable(self):
        response = self.parent.parent.conn.programDisable(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not disable program: '
                                           + self._id)
        else:
            self.parent.parent.log.info('ISY disabled program: ' + self._id)
            self.update(_change2update_interval)

    def enableRunAtStartup(self):
        response = self.parent.parent.conn.programEnableRunAtStartup(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not enable run at '
                                           + 'startup for program: '
                                           + self._id)
        else:
            self.parent.parent.log.info('ISY enabled run at startup for '
                                        + 'program: ' + self._id)
            self.update(_change2update_interval)

    def disableRunAtStartup(self):
        response = self.parent.parent.conn.programDisableRunAtStartup(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not disable run at '
                                           + 'startup for program: '
                                           + self._id)
        else:
            self.parent.parent.log.info('ISY disabled run at startup for '
                                        + 'program: ' + self._id)
            self.update(_change2update_interval)
