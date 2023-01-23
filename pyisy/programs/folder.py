"""ISY Program Folders."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from pyisy.constants import (
    CMD_DISABLE,
    CMD_ENABLE,
    CMD_RUN,
    CMD_RUN_ELSE,
    CMD_RUN_THEN,
    CMD_STOP,
    URL_PROGRAMS,
    Protocol,
)
from pyisy.helpers.entity import BoolStrT, Entity, EntityDetail
from pyisy.helpers.events import EventEmitter
from pyisy.logging import _LOGGER

if TYPE_CHECKING:
    from pyisy.programs import Programs


# Receiving exact keys from ISY, ignore naming issues
# pylint: disable=invalid-name
@dataclass
class FolderDetail(EntityDetail):
    """Details for the folder entity."""

    id: str = ""
    name: str = ""
    status: BoolStrT = "not_loaded"
    folder: bool = False
    last_finish_time: datetime | None = None
    last_run_time: datetime | None = None
    next_scheduled_run_time: datetime | None = None


class Folder(Entity[FolderDetail, BoolStrT]):
    """Object representing a program folder on the ISY device."""

    def __init__(
        self, platform: Programs, address: str, name: str, detail: FolderDetail
    ) -> None:
        """Initialize the Folder class."""
        self.status_events = EventEmitter()
        self.platform = platform
        self.isy = platform.isy
        self._protocol = Protocol.FOLDER
        self._address = address
        self._name = name
        self._last_update = datetime.now()
        self._status = detail.status
        self.detail = detail

    async def send_cmd(self, command: str) -> bool:
        """Run the appropriate clause of the object."""
        req_url = self.isy.conn.compile_url([URL_PROGRAMS, self.address, command])
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
