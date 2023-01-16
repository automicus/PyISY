"""ISY Program Folders."""
from __future__ import annotations

from datetime import datetime

from pyisy.constants import (
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
from pyisy.entity import Entity
from pyisy.logging import _LOGGER


class Folder(Entity):
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

    def __init__(self, programs, address, pname, pstatus, plastup):
        """Initialize the Folder class."""
        self._address = address
        self._protocol = PROTO_FOLDER
        self._last_update = plastup
        self._name = pname
        self._programs = programs
        self._status = pstatus
        self.isy = programs.isy

    @property
    def leaf(self):
        """Get the leaf property."""
        return self

    async def update(self, wait_time=UPDATE_INTERVAL, data=None):
        """
        Update the status of the program.

        |  data: [optional] The data to update the folder with.
        |  wait_time: [optional] Seconds to wait before updating.
        """
        if data is not None:
            self._last_changed = datetime.now()
            self.update_status(data["pstatus"])
            return
        await self._programs.update(wait_time=wait_time, address=self.address)

    async def send_cmd(self, command):
        """Run the appropriate clause of the object."""
        req_url = self.isy.conn.compile_url([URL_PROGRAMS, str(self.address), command])
        result = await self.isy.conn.request(req_url)
        if not result:
            _LOGGER.warning(
                'ISY could not call "%s" on program: %s', command, self.address
            )
            return False
        _LOGGER.debug('ISY ran "%s" on program: %s', command, self.address)
        if not self.isy.auto_update:
            await self.update()
        return True

    async def enable(self):
        """Send command to the program/folder to enable it."""
        return await self.send_cmd(CMD_ENABLE)

    async def disable(self):
        """Send command to the program/folder to enable it."""
        return await self.send_cmd(CMD_DISABLE)

    async def run(self):
        """Send a run command to the program/folder."""
        return await self.send_cmd(CMD_RUN)

    async def run_then(self):
        """Send a runThen command to the program/folder."""
        return await self.send_cmd(CMD_RUN_THEN)

    async def run_else(self):
        """Send a runElse command to the program/folder."""
        return await self.send_cmd(CMD_RUN_ELSE)

    async def stop(self):
        """Send a stop command to the program/folder."""
        return await self.send_cmd(CMD_STOP)
