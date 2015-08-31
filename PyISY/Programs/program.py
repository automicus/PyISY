from ..constants import _change2update_interval
from ..constants import _empty_time
from VarEvents import Property
from .folder import Folder


class Program(Folder):
    """
    Class representing a program on the ISY controller.

    |  parent: The program manager object.
    |  pid: The ID of the program.
    |  pname: The name of the program.
    |  pstatus: The current status of the program.
    |  plastup: The last time the program was updated.
    |  plastrun: The last time the program was run.
    |  plastfin: The last time the program finished running.
    |  penabled: Boolean value showing if the program is enabled on the
                 controller.
    |  pstartrun: Boolean value showing if the if the program runs on
                  controller start up.
    |  prunning: Boolean value showing if the current program is running
                 on the controller.

    :ivar name: The name of the program.
    :ivar status: Watched property representing the current status of the
                  program.
    :ivar lastUpdate: Watched property representing the last time the program
                      was updated.
    :ivar lastRun: Watched property representing the last time the program was
                   run.
    :ivar lastFinished: Watched property representing the last time the program
                        finished running.
    :ivar enabled: Watched property representing if the program is enabled on
                   the controller.
    :ivar runAtStartup: Watched property representing the if the program runs on
                        controller start up.
    :ivar running: Watched property representing if the current program is
                   running on the controller.
    """

    lastUpdate = Property(_empty_time, readonly=True)
    lastRun = Property(_empty_time, readonly=True)
    lastFinished = Property(_empty_time, readonly=True)
    enabled = Property(True)
    runAtStartup = Property(True)
    running = Property(False, readonly=True)
    ranThen = Property(0, readonly=True)
    ranElse = Property(0, readonly=True)
    dtype = 'program'

    def __init__(self, parent, pid, pname, pstatus, plastup, plastrun, plastfin,
                 penabled, pstartrun, prunning):
        super(Program, self).__init__(parent, pid, pname, pstatus)
        self.lastUpdate.update(plastup, force=True, silent=True)
        self.lastRun.update(plastrun, force=True, silent=True)
        self.lastFinished.update(plastfin, force=True, silent=True)
        self.enabled.update(penabled, force=True, silent=True)
        self.enabled.responder = self.__report_enabled__
        self.runAtStartup.update(pstartrun, force=True, silent=True)
        self.runAtStartup.responder = self.__report_startrun__
        self.running.update(prunning, force=True, silent=True)

    def __str__(self):
        """ Returns a string representation of the object. """
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
        """
        Update the program with values on the controller.

        |  waitTime: [optional] Seconds to wait before updating.
        |  data: [optional] Data to update the object with.
        """
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
        """ Enable the program on the controller. """
        response = self.parent.parent.conn.programEnable(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not enable program: '
                                           + self._id)
            return False
        else:
            self.parent.parent.log.info('ISY enabled program: ' + self._id)
            self.update(_change2update_interval)
            return True

    def disable(self):
        """ Disable the program on the controller. """
        response = self.parent.parent.conn.programDisable(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not disable program: '
                                           + self._id)
            return False
        else:
            self.parent.parent.log.info('ISY disabled program: ' + self._id)
            self.update(_change2update_interval)
            return True

    def enableRunAtStartup(self):
        """ Enable running the program on controller start up. """
        response = self.parent.parent.conn.programEnableRunAtStartup(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not enable run at '
                                           + 'startup for program: '
                                           + self._id)
            return False
        else:
            self.parent.parent.log.info('ISY enabled run at startup for '
                                        + 'program: ' + self._id)
            self.update(_change2update_interval)
            return True

    def disableRunAtStartup(self):
        """ Disable running the program on controller start up. """
        response = self.parent.parent.conn.programDisableRunAtStartup(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not disable run at '
                                           + 'startup for program: '
                                           + self._id)
            return False
        else:
            self.parent.parent.log.info('ISY disabled run at startup for '
                                        + 'program: ' + self._id)
            self.update(_change2update_interval)
            return True
