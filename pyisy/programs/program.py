"""Representation of a program from the ISY."""
from ..constants import (
    CMD_DISABLE_RUN_AT_STARTUP,
    CMD_ENABLE_RUN_AT_STARTUP,
    PROTO_PROGRAM,
    TAG_PROGRAM,
    UPDATE_INTERVAL,
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
    """

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
        super().__init__(programs, address, pname, pstatus, plastup)
        self._enabled = penabled
        self._last_finished = plastfin
        self._last_run = plastrun
        self._ran_else = 0
        self._ran_then = 0
        self._run_at_startup = pstartrun
        self._running = prunning

    @property
    def enabled(self):
        """Return if the program is enabled on the controller."""
        return self._enabled

    @enabled.setter
    def enabled(self, value):
        """Set if the program is enabled on the controller."""
        if self._enabled != value:
            self._enabled = value
        return self._enabled

    @property
    def last_finished(self):
        """Return the last time the program finished running."""
        return self._last_finished

    @last_finished.setter
    def last_finished(self, value):
        """Set the last time the program finished running."""
        if self._last_finished != value:
            self._last_finished = value
        return self._last_finished

    @property
    def last_run(self):
        """Return the last time the program was run."""
        return self._last_run

    @last_run.setter
    def last_run(self, value):
        """Set the last time the program was run."""
        if self._last_run != value:
            self._last_run = value
        return self._last_run

    @property
    def protocol(self):
        """Return the protocol for this entity."""
        return PROTO_PROGRAM

    @property
    def ran_else(self):
        """Return the Ran Else property for this program."""
        return self._ran_else

    @ran_else.setter
    def ran_else(self, value):
        """Set the Ran Else property for this program."""
        if self._ran_else != value:
            self._ran_else = value
        return self._ran_else

    @property
    def ran_then(self):
        """Return the Ran Then property for this program."""
        return self._ran_then

    @ran_then.setter
    def ran_then(self, value):
        """Set the Ran Then property for this program."""
        if self._ran_then != value:
            self._ran_then = value
        return self._ran_then

    @property
    def run_at_startup(self):
        """Return if the program runs on controller start up."""
        return self._run_at_startup

    @run_at_startup.setter
    def run_at_startup(self, value):
        """Set if the program runs on controller start up."""
        if self._run_at_startup != value:
            self._run_at_startup = value
        return self._run_at_startup

    @property
    def running(self):
        """Return if the current program is running on the controller."""
        return self._running

    @running.setter
    def running(self, value):
        """Set if the current program is running on the controller."""
        if self._running != value:
            self._running = value
        return self._running

    async def update(self, wait_time=UPDATE_INTERVAL, data=None):
        """
        Update the program with values on the controller.

        |  wait_time: [optional] Seconds to wait before updating.
        |  data: [optional] Data to update the object with.
        """
        if data is not None:
            self._enabled = data["penabled"]
            self._last_finished = data["plastfin"]
            self._last_run = data["plastrun"]
            self._last_update = data["plastup"]
            self._run_at_startup = data["pstartrun"]
            self._running = (data["plastrun"] >= data["plastup"]) or data["prunning"]
            # Update Status last and make sure the change event fires, but only once.
            if self.status != data["pstatus"]:
                self.status = data["pstatus"]
            else:
                # Status didn't change, but something did, so fire the event.
                self.status_events.notify(self.status)
            return
        await self._programs.update(wait_time, address=self._id)

    async def enable_run_at_startup(self):
        """Send command to the program to enable it to run at startup."""
        return await self.send_cmd(CMD_ENABLE_RUN_AT_STARTUP)

    async def disable_run_at_startup(self):
        """Send command to the program to enable it to run at startup."""
        return await self.send_cmd(CMD_DISABLE_RUN_AT_STARTUP)
