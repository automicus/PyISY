"""Representation of a program from the ISY."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pyisy.constants import (
    CMD_DISABLE_RUN_AT_STARTUP,
    CMD_ENABLE_RUN_AT_STARTUP,
    Protocol,
)
from pyisy.helpers.entity import BoolStrT, Entity
from pyisy.programs.folder import Folder, FolderDetail

if TYPE_CHECKING:
    from pyisy.programs import Programs


# Receiving exact keys from ISY, ignore naming issues
# pylint: disable=invalid-name
@dataclass
class ProgramDetail(FolderDetail):
    """Details for the program entity."""

    enabled: bool = True
    run_at_startup: bool = False
    running: str = ""


class Program(Folder, Entity[ProgramDetail, BoolStrT]):
    """Class representing a program on the ISY controller."""

    def __init__(
        self, platform: Programs, address: str, name: str, detail: ProgramDetail
    ) -> None:
        """Initialize a Program class."""
        super().__init__(platform, address, name, detail)
        self._protocol = Protocol.PROGRAM
        self._enabled = detail.enabled

    async def enable_run_at_startup(self) -> bool:
        """Send command to the program to enable it to run at startup."""
        return await self.send_cmd(CMD_ENABLE_RUN_AT_STARTUP)

    async def disable_run_at_startup(self) -> bool:
        """Send command to the program to enable it to run at startup."""
        return await self.send_cmd(CMD_DISABLE_RUN_AT_STARTUP)
