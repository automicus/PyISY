"""Message EventRouter for ISY Event Stream Messages."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from typing import TYPE_CHECKING, Any, cast

from pyisy.exceptions import ISYResponseParseError
from pyisy.helpers.xml import parse_xml
from pyisy.logging import LOG_VERBOSE
from pyisy.nodes.node_events import (
    node_changed_received,
    node_update_received,
    progress_report_received,
)
from pyisy.util.backports import StrEnum

if TYPE_CHECKING:
    from pyisy.events.tcpsocket import EventStream
    from pyisy.events.websocket import WebSocketClient
    from pyisy.isy import ISY

_LOGGER = logging.getLogger(__name__)


class Action(StrEnum):
    """Action String Enum."""

    EVENT_STATUS = "0"
    GET_STATUS = "1"
    KEY_CHANGED = "2"
    INFO_STRING = "3"
    IR_LEARN = "4"
    SCHEDULE = "5"
    VAR_STATUS = "6"
    VAR_INIT = "7"
    KEY = "8"


class ControlEvent(StrEnum):
    """Trigger Event String Enum."""

    HEARTBEAT = "_0"
    TRIGGER = "_1"
    DRIVER_SPECIFIC = "_2"
    NODE_CHANGED = "_3"
    SYSTEM_CONFIG_UPDATED = "_4"
    SYSTEM_STATUS = "_5"
    INTERNET_ACCESS = "_6"
    PROGRESS_REPORT = "_7"
    SECURITY_SYSTEM = "_8"
    SYSTEM_ALERT = "_9"  # Not Implemented
    OPENADR = "_10"
    CLIMATE_EVENTS = "_11"
    AMI_SEP = "_12"
    EXTERNAL_ENERGY_MONITORING = "_13"
    UPB_LINKER = "_14"
    UPB_DEVICE_ADDER = "_15"
    UPB_DEVICE_STATUS = "_16"
    GAS_METER = "_17"
    ZIGBEE = "_18"
    ELK = "_19"
    DEVICE_LINKER = "_20"
    Z_WAVE = "_21"
    BILLING = "_22"
    PORTAL = "_23"


class ConfigAction(StrEnum):
    """Trigger Event String Enum."""

    TIME_CHANGED = "0"
    TIME_CONFIGURATION = "1"
    NTP_SETTINGS = "2"
    NOTIFICATIONS_SETTINGS = "3"
    NTP_COMMUNICATIONS_ERROR = "4"
    BATCH_MODE = "5"
    BATTERY_MODE_PROGRAMMING = "6"


TIME_UPDATE = [
    ConfigAction.TIME_CHANGED,
    ConfigAction.TIME_CONFIGURATION,
    ConfigAction.NTP_SETTINGS,
    ConfigAction.NOTIFICATIONS_SETTINGS,
    ConfigAction.NTP_COMMUNICATIONS_ERROR,
]


class SecuritySystemAction(StrEnum):
    """Actions for security system."""

    DISCONNECTED = "0"
    CONNECTED = "1"
    DISARMED = "DA"
    ARMED_AWAY = "AW"
    ARMED_STAY = "AS"
    ARMED_STAY_INSTANT = "ASI"
    ARMED_NIGHT = "AN"
    ARMED_NIGHT_INSTANT = "ANI"
    ARMED_VACATION = "AV"


@dataclass
class EventData:
    """Dataclass to represent the event data returned from the stream."""

    seqnum: str = ""
    sid: str = ""
    control: str = ""
    action: dict[str, Any] | str | None = None
    node: str | None = None
    event_info: str | None = None
    fmt_act: str | None = None


class EventRouter:
    """Class to represent the message router for the event stream."""

    isy: ISY
    events: EventStream | WebSocketClient
    _stream_id: str = ""
    key: str = ""
    _loaded: bool = False

    def __init__(self, events: EventStream | WebSocketClient) -> None:
        """Initialize a new router class."""
        self.isy = events.isy
        self.events = events
        self.t_0: float = 0

    async def parse_message(self, msg: str) -> None:
        """Parse a message from the event stream and pass to router."""
        # VERBOSE logging will print the raw XML
        _LOGGER.log(LOG_VERBOSE, msg)
        try:
            xml_dict = parse_xml(msg)
        except ISYResponseParseError:
            _LOGGER.warning("Received malformed XML:\n%s", msg)
            return

        # A wild stream id appears!
        if (sid := xml_dict.get("s_i_d")) and self._stream_id == "":
            self._stream_id = sid
            self.events.update_stream_id(sid)
        elif event := xml_dict.get("event", {}):
            try:
                await self.route_message(EventData(**event))
            except (KeyError, ValueError, NameError):
                _LOGGER.error("Could not validate event", exc_info=True)

    async def route_message(self, event: EventData) -> None:
        """Route a received message from the event stream.

        https://www.universal-devices.com/docs/production/The+ISY994+Developer+Cookbook.pdf
        """
        # Enable the following and disable VERBOSE line above for JSON output:
        # _LOGGER.log(
        #     LOG_VERBOSE,
        #     "Event: %s",
        #     json.dumps(event.__dict__, indent=4, default=str),
        # )

        # direct the event message
        if not (control := event.control):
            return
        if (
            control == ControlEvent.HEARTBEAT and event.action is not None
        ):  # ISY HEARTBEAT
            self.events.heartbeat(int(cast(str, event.action)))
        elif control[0] != "_":  # NODE CONTROL EVENT
            if self.isy.nodes.loaded and self.isy.nodes.initialized:
                await node_update_received(self.isy.nodes, event)
        elif control == ControlEvent.TRIGGER:  # Trigger Update
            if event.action == Action.EVENT_STATUS:
                # Event Status
                if self.isy.programs.loaded:
                    await self.isy.programs.update_received(event)
            if event.action == Action.GET_STATUS:
                # Get Status (subscribers should refresh)
                if self.isy.nodes.initialized:
                    await self.isy.nodes.update_status()
            if event.action == Action.KEY_CHANGED:
                # Key Changed (node = key)
                self.key = cast(str, event.node)
                _LOGGER.debug("Key changed: %s", self.key)
                return
            if event.action in {
                Action.INFO_STRING,
                Action.IR_LEARN,
            }:  # Info string, IR Learn mode
                return
            if event.action == Action.SCHEDULE:
                # Schedule status changed (node=key)
                return
            if event.action == Action.VAR_STATUS:
                # Variable status changed
                if self.isy.variables.loaded:
                    await self.isy.variables.update_received(event)
                return
            if event.action == Action.VAR_INIT:
                # Variable init value set
                if self.isy.variables.loaded:
                    await self.isy.variables.update_received(event, init=True)
                return
            if event.action == Action.KEY:
                # Key (event_info = key)
                self.key = cast(str, event.event_info)
                _LOGGER.debug("Key received: %s", self.key)
                return
        elif control == ControlEvent.DRIVER_SPECIFIC:
            # Driver specific events
            _LOGGER.debug(
                "Driver specific event: %s",
                json.dumps(event.__dict__, default=str),
            )
            return
        elif control == ControlEvent.NODE_CHANGED:
            # Node Changed/Updated
            await node_changed_received(self.isy.nodes, event)
            return
        elif control == ControlEvent.SYSTEM_CONFIG_UPDATED:
            # System Configuration Updated
            if event.action in TIME_UPDATE:
                if self.isy.clock.loaded:
                    await self.isy.clock.update()
                return
            if event.action == ConfigAction.BATCH_MODE:
                # <eventInfo>
                # <status>"1"|"0"</status>
                # </eventInfo>
                _LOGGER.info(
                    "Batch mode changed to: %s",
                    json.dumps(event.__dict__, default=str),
                )
            if event.action == ConfigAction.BATTERY_MODE_PROGRAMMING:
                # <eventInfo>
                # <status>"1"|"0"</status>
                # </eventInfo>
                _LOGGER.info(
                    "Battery programming mode changed to: %s",
                    json.dumps(event.__dict__, default=str),
                )
            return
        elif control == ControlEvent.SYSTEM_STATUS:
            # System Status Changed
            self.isy.system_status_changed_received(event.action)
            return
        elif control == ControlEvent.PROGRESS_REPORT:
            # Progress report, device programming event
            await progress_report_received(self.isy.nodes, event)
            return
        elif control == ControlEvent.SECURITY_SYSTEM:
            # Security System Control Event
            _LOGGER.debug(
                "Security System Control Event: %s",
                json.dumps(event.__dict__, default=str),
            )
            return
        elif control == ControlEvent.ELK:
            # ELK Control Event
            _LOGGER.debug(
                "ELK Control Event: %s",
                json.dumps(event.__dict__, default=str),
            )
            return
        elif control == ControlEvent.Z_WAVE:
            # Z-Wave Control Event
            _LOGGER.debug(
                "Z-Wave Control Event: %s",
                json.dumps(event.__dict__, default=str),
            )
            return
        _LOGGER.info(
            "Other Control Event: %s %s",
            ControlEvent(control).name,
            json.dumps(event.__dict__, default=str),
        )
