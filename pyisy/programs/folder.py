"""ISY Program Folders."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from ..constants import (
    ATTR_LAST_CHANGED,
    ATTR_LAST_UPDATE,
    ATTR_STATUS,
    CMD_DISABLE,
    CMD_ENABLE,
    CMD_RUN,
    CMD_RUN_ELSE,
    CMD_RUN_THEN,
    CMD_STOP,
    PROTO_FOLDER,
    TAG_ADDRESS,
    TAG_FOLDER,
    UPDATE_INTERVAL,
    URL_PROGRAMS,
)
from ..helpers import EventEmitter, now
from ..logging import _LOGGER

if TYPE_CHECKING:
    from . import Programs


class Folder:
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

    def __init__(self, programs: Programs, address: str, pname: str, pstatus: int, plastup: datetime) -> None:
        """Initialize the Folder class."""
        self._id = address
        self._last_update = plastup
        self._last_changed = now()
        self._name = pname
        self._programs = programs
        self._status = pstatus
        self.isy = programs.isy
        self.status_events = EventEmitter()

    def __str__(self) -> str:
        """Return a string representation of the node."""
        return f"{type(self).__name__}({self._id})"

    @property
    def address(self) -> str:
        """Return the program or folder ID."""
        return self._id

    @property
    def last_changed(self) -> datetime:
        """Return the last time the program was changed in this module."""
        return self._last_changed

    @last_changed.setter
    def last_changed(self, value: datetime) -> datetime:
        """Set the last time the program was changed."""
        if self._last_changed != value:
            self._last_changed = value
        return self._last_changed

    @property
    def last_update(self) -> datetime:
        """Return the last time the program was updated."""
        return self._last_update

    @last_update.setter
    def last_update(self, value: datetime) -> datetime:
        """Set the last time the program was updated."""
        if self._last_update != value:
            self._last_update = value
        return self._last_update

    @property
    def leaf(self) -> Folder:
        """Get the leaf property."""
        return self

    @property
    def name(self) -> str:
        """Return the name of the Node."""
        return self._name

    @property
    def protocol(self) -> str:
        """Return the protocol for this entity."""
        return PROTO_FOLDER

    @property
    def status(self) -> int:
        """Return the current node state."""
        return self._status

    @status.setter
    def status(self, value: int) -> int:
        """Set the current node state and notify listeners."""
        if self._status != value:
            self._status = value
            self.status_events.notify(self._status)
        return self._status

    @property
    def status_feedback(self) -> dict[str, Any]:
        """Return information for a status change event."""
        return {
            TAG_ADDRESS: self.address,
            ATTR_STATUS: self._status,
            ATTR_LAST_CHANGED: self._last_changed,
            ATTR_LAST_UPDATE: self._last_update,
        }

    def _update(self, data: dict[str, Any]) -> None:
        """Update the folder with values from the controller."""
        self._last_changed = now()
        self.status = data["pstatus"]

    async def update(self, wait_time: float = UPDATE_INTERVAL, data: dict[str, Any] | None = None) -> None:
        """
        Update the status of the program.

        |  data: [optional] The data to update the folder with.
        |  wait_time: [optional] Seconds to wait before updating.
        """
        if data is not None:
            self._update(data)
            return
        await self._programs.update(wait_time=wait_time, address=self._id)

    async def send_cmd(self, command: str) -> bool:
        """Run the appropriate clause of the object."""
        req_url = self.isy.conn.compile_url([URL_PROGRAMS, str(self._id), command])
        result = await self.isy.conn.request(req_url)
        if not result:
            _LOGGER.warning('ISY could not call "%s" on program: %s', command, self._id)
            return False
        _LOGGER.debug('ISY ran "%s" on program: %s', command, self._id)
        if not self.isy.auto_update:
            await self.update()
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
