"""Init for management of ISY Programs."""
from __future__ import annotations

import asyncio
from dataclasses import asdict
from enum import IntEnum
import json
from typing import TYPE_CHECKING, Any, cast

from dateutil import parser

from pyisy.constants import TAG_FOLDER, URL_PROGRAMS, URL_SUBFOLDERS, XML_TRUE
from pyisy.helpers.entity_platform import EntityPlatform
from pyisy.helpers.events import EventEmitter
from pyisy.helpers.models import EventData
from pyisy.logging import _LOGGER, LOG_VERBOSE
from pyisy.programs.folder import Folder, FolderDetail
from pyisy.programs.program import Program, ProgramDetail

if TYPE_CHECKING:
    from pyisy.isy import ISY

PLATFORM = "programs"
TRUE = "true"


class RunningStatus(IntEnum):
    """Program running status enum."""

    IDLE = 0x01
    RUNNING_THEN = 0x02
    RUNNING_ELSE = 0x03


class ProgramStatus(IntEnum):
    """Program condition status enum."""

    UNKNOWN = 0x1
    TRUE = 0x2
    FALSE = 0x3
    NOT_LOADED = 0xF


ProgramsT = Folder | Program


class Programs(EntityPlatform[ProgramsT]):
    """This class handles the ISY programs."""

    def __init__(
        self,
        isy: ISY,
    ) -> None:
        """Initialize the Programs ISY programs manager class.

        Iterate over self.values()
        """
        super().__init__(isy=isy, platform_name=PLATFORM)
        self.status_events = EventEmitter()
        self.url = self.isy.conn.compile_url([URL_PROGRAMS], {URL_SUBFOLDERS: XML_TRUE})

    def parse(self, xml_dict: dict[str, Any]) -> None:
        """Parse the results from the ISY."""
        if not (features := xml_dict["programs"]["program"]):
            return

        for feature in features:
            self.parse_entity(feature)
        _LOGGER.info("Loaded %s", PLATFORM)

    def parse_entity(self, feature: dict[str, Any]) -> None:
        """Parse a single value and add it to the platform."""
        try:
            address = feature["id"]
            name = feature["name"]
            _LOGGER.log(LOG_VERBOSE, "Parsing %s: %s (%s)", PLATFORM, name, address)

            if feature[TAG_FOLDER]:
                entity = Folder(self, address, name, FolderDetail(**feature))
            else:
                entity = Program(self, address, name, ProgramDetail(**feature))

            self.add_or_update_entity(address, name, entity)
        except (TypeError, KeyError, ValueError) as exc:
            _LOGGER.exception("Error loading %s: %s", PLATFORM, exc)

    def update_received(self, event: EventData) -> None:
        """Update programs from EventStream message.

        <eventInfo>
        <id></id>
        <X/> ... X=on if enabled, and off if disabled
        <Y/> ... Y=rr if run at reboot and nr if not run at reboot
        <r> last run time in YYMMDD HH:MM:SS</r>
        <f> last finish time in YYMMDD HH:MM:SS</f>
        <s> status* </s>
        </var>
        </eventInfo>
        """
        event_info = cast(dict, event.event_info)
        if (address := cast(str, event_info["id"]).zfill(4)) not in self.addresses:
            # New/unknown program, refresh full set.
            update_task = asyncio.create_task(self.update())
            self.isy.background_tasks.add(update_task)
            update_task.add_done_callback(self.isy.background_tasks.discard)
            return
        entity = self.entities[address]
        detail = cast(ProgramDetail, entity.detail)

        if "on" in event_info:
            detail.enabled = True
        elif "off" in event_info:
            detail.enabled = False

        if "rr" in event_info:
            detail.run_at_startup = True
        elif "nr" in event_info:
            detail.run_at_startup = False

        if status := event_info.get("s"):
            # Status is a bitwise OR of RUN_X and ST_X:
            detail.status = ProgramStatus(int(status[0], 16)).name.lower()
            detail.running = RunningStatus(int(status[1])).name.lower()

        if last_run := event_info.get("r"):
            detail.last_run_time = parser.parse(last_run)

        if last_finish := event_info.get("f"):
            detail.last_finish_time = parser.parse(last_finish)

        entity.update_status(entity.status, force=True)

        _LOGGER.debug(
            "Updated program: address=%s, detail=%s",
            address,
            json.dumps(asdict(detail), default=str),
        )
