"""Representation of a program from the ISY."""
from VarEvents import Property

from ..constants import (
    CMD_DISABLE,
    CMD_DISABLE_RUN_AT_STARTUP,
    CMD_ENABLE,
    CMD_ENABLE_RUN_AT_STARTUP,
    EMPTY_TIME,
    PROTO_PROGRAM,
    TAG_PROGRAM,
)
from .folder import Folder


class Program(Folder):
    """
    Class representing a program on the ISY controller.

    |  programs: The program manager object.
    |  address: The ID of the program.
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
    :ivar runAtStartup: Watched property representing the if the program runs
                        on controller start up.
    :ivar running: Watched property representing if the current program is
                   running on the controller.
    """

    lastUpdate = Property(EMPTY_TIME, readonly=True)
    lastRun = Property(EMPTY_TIME, readonly=True)
    lastFinished = Property(EMPTY_TIME, readonly=True)
    enabled = Property(True)
    runAtStartup = Property(True)
    running = Property(False, readonly=True)
    ranThen = Property(0, readonly=True)
    ranElse = Property(0, readonly=True)
    dtype = TAG_PROGRAM

    def __init__(
        self,
        programs,
        address,
        pname,
        pstatus,
        plastup,
        plastrun,
        plastfin,
        penabled,
        pstartrun,
        prunning,
    ):
        """Initialize a Program class."""
        super(Program, self).__init__(programs, address, pname, pstatus)
        self.lastUpdate.update(plastup, force=True, silent=True)
        self.lastRun.update(plastrun, force=True, silent=True)
        self.lastFinished.update(plastfin, force=True, silent=True)
        self.enabled.update(penabled, force=True, silent=True)
        self.enabled.responder = self.__report_enabled__
        self.runAtStartup.update(pstartrun, force=True, silent=True)
        self.runAtStartup.responder = self.__report_startrun__
        self.running.update(prunning, force=True, silent=True)

    def __report_enabled__(self, val):
        """Set the enabled flag."""
        self.noupdate = True
        self.send_pgrm_cmd(CMD_ENABLE if val else CMD_DISABLE)
        self.noupdate = False

    def __report_startrun__(self, val):
        """Set the run at startup flag."""
        self.noupdate = True
        self.send_pgrm_cmd(
            CMD_ENABLE_RUN_AT_STARTUP if val else CMD_DISABLE_RUN_AT_STARTUP
        )
        self.noupdate = False

    def update(self, wait_time=0, data=None):
        """
        Update the program with values on the controller.

        |  wait_time: [optional] Seconds to wait before updating.
        |  data: [optional] Data to update the object with.
        """
        if not self.noupdate:
            if data is not None:
                prunning = (data["plastrun"] >= data["plastup"]) or data["prunning"]
                self.status.update(data["pstatus"], force=True, silent=True)
                self.lastUpdate.update(data["plastup"], force=True, silent=True)
                self.lastRun.update(data["plastrun"], force=True, silent=True)
                self.lastFinished.update(data["plastfin"], force=True, silent=True)
                self.enabled.update(data["penabled"], force=True, silent=True)
                self.runAtStartup.update(data["pstartrun"], force=True, silent=True)
                self.running.update(prunning, force=True, silent=True)
            elif not self.isy.auto_update:
                self._programs.update(wait_time, address=self._id)

    @property
    def protocol(self):
        """Return the protocol for this entity."""
        return PROTO_PROGRAM
