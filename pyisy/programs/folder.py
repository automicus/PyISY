"""ISY Program Folders."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

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
from pyisy.helpers.entity import Entity
from pyisy.helpers.events import EventEmitter
from pyisy.logging import _LOGGER

if TYPE_CHECKING:
    from pyisy.programs import Programs


class Folder(Entity):
    """Object representing a program folder on the ISY device."""

    dtype = TAG_FOLDER

    def __init__(
        self, platform: Programs, address: str, name: str, detail: dict
    ) -> None:
        """Initialize the Folder class."""
        self.status_events = EventEmitter()
        self.platform = platform
        self.isy = platform.isy
        self._protocol = PROTO_FOLDER
        self._address = address
        self._name = name
        self._last_update = detail["plastup"]
        self._status = detail["pstatus"]

    @property
    def leaf(self) -> Folder:
        """Get the leaf property."""
        return self

    async def update(self, wait_time=UPDATE_INTERVAL, data=None) -> None:
        """
        Update the status of the program.

        |  data: [optional] The data to update the folder with.
        |  wait_time: [optional] Seconds to wait before updating.
        """
        if data is not None:
            self._last_changed = datetime.now()
            self.update_status(data["pstatus"])
            return
        await self.platform.update(wait_time=wait_time, address=self.address)

    async def send_cmd(self, command) -> bool:
        """Run the appropriate clause of the object."""
        req_url = self.isy.conn.compile_url([URL_PROGRAMS, str(self.address), command])
        result = await self.isy.conn.request(req_url)
        if not result:
            _LOGGER.warning(
                'ISY could not call "%s" on program: %s', command, self.address
            )
            return False
        _LOGGER.debug('ISY ran "%s" on program: %s', command, self.address)
        return True

    async def enable(self) -> bool:
        """Send command to the program/folder to enable it."""
        return await self.send_cmd(CMD_ENABLE)

    async def disable(self) -> bool:
        """Send command to the program/folder to enable it."""
        return await self.send_cmd(CMD_DISABLE)

    async def run(self) -> bool:
        """Send a run command to the program/folder."""
        return await self.send_cmd(CMD_RUN)

    async def run_then(self) -> bool:
        """Send a runThen command to the program/folder."""
        return await self.send_cmd(CMD_RUN_THEN)

    async def run_else(self) -> bool:
        """Send a runElse command to the program/folder."""
        return await self.send_cmd(CMD_RUN_ELSE)

    async def stop(self) -> bool:
        """Send a stop command to the program/folder."""
        return await self.send_cmd(CMD_STOP)
