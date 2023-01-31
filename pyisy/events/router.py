"""Message EventRouter for ISY Event Stream Messages."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import logging
from typing import TYPE_CHECKING, Any, cast

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
    ZMATTER_Z_WAVE = "_25"


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
    event_info: dict[str, Any] | str | None = None
    fmt_act: str | None = None
    fmt_name: str | None = None


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

    def parse_message(self, msg: str) -> None:
        """Parse a message from the event stream and pass to router."""
        # VERBOSE logging will print the raw XML
        _LOGGER.log(LOG_VERBOSE, msg)
        xml_dict = parse_xml(msg)

        # A wild stream id appears!
        if (sid := xml_dict.get("sid")) and self._stream_id == "":
            self._stream_id = sid
            self.events.update_stream_id(sid)
            return
        if event := xml_dict.get("event", {}):
            try:
                self.route_message(EventData(**event))
            except (KeyError, ValueError, NameError):
                _LOGGER.error("Could not validate event", exc_info=True)

    def route_message(self, event: EventData) -> None:
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
            return
        if control[0] != "_":  # NODE CONTROL EVENT
            if self.isy.nodes.loaded and self.isy.nodes.initialized:
                node_update_received(self.isy.nodes, event)
            return
        if control == ControlEvent.TRIGGER:  # Trigger Update
            if event.action == Action.EVENT_STATUS:
                # Event Status
                if self.isy.programs.loaded:
                    self.isy.programs.update_received(event)
            if event.action == Action.GET_STATUS:
                # Get Status (subscribers should refresh)
                if self.isy.nodes.initialized:
                    update_status_task = asyncio.create_task(
                        self.isy.nodes.update_status()
                    )
                    self.isy.background_tasks.add(update_status_task)
                    update_status_task.add_done_callback(
                        self.isy.background_tasks.discard
                    )
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
                    self.isy.variables.update_received(event)
                return
            if event.action == Action.VAR_INIT:
                # Variable init value set
                if self.isy.variables.loaded:
                    self.isy.variables.update_received(event, init=True)
                return
            if event.action == Action.KEY:
                # Key (event_info = key)
                self.key = cast(str, event.event_info)
                _LOGGER.debug("Key received: %s", self.key)
                return
            return
        if control == ControlEvent.DRIVER_SPECIFIC:
            # Driver specific events
            _LOGGER.debug(
                "Driver specific event: %s",
                json.dumps(event.__dict__, default=str),
            )
            return
        if control == ControlEvent.NODE_CHANGED:
            # Node Changed/Updated
            node_changed_received(self.isy.nodes, event)
            return
        if control == ControlEvent.SYSTEM_CONFIG_UPDATED:
            # System Configuration Updated
            if event.action in TIME_UPDATE:
                if self.isy.clock.loaded:
                    update_status_task = asyncio.create_task(self.isy.clock.update())
                    self.isy.background_tasks.add(update_status_task)
                    update_status_task.add_done_callback(
                        self.isy.background_tasks.discard
                    )
                return
            if event.action == ConfigAction.BATCH_MODE:
                self.isy.diagnostics.batch_mode = (
                    cast(dict, event.event_info)["status"] == "1"
                )
                _LOGGER.debug(
                    "Batch mode changed to: %s",
                    self.isy.diagnostics.batch_mode,
                )
            if event.action == ConfigAction.BATTERY_MODE_PROGRAMMING:
                self.isy.diagnostics.write_updates_to_battery_nodes = (
                    cast(dict, event.event_info)["status"] == "1"
                )
                _LOGGER.debug(
                    "Battery programming mode changed to: %s",
                    self.isy.diagnostics.write_updates_to_battery_nodes,
                )
            return
        if control == ControlEvent.SYSTEM_STATUS:
            # System Status Changed
            self.isy.system_status_changed_received(event.action)
            return
        if control == ControlEvent.PROGRESS_REPORT:
            # Progress report, device programming event
            progress_report_received(self.isy.nodes, event)
            return
        if control == ControlEvent.SECURITY_SYSTEM:
            # Security System Control Event
            _LOGGER.debug(
                "Security System Control Event: %s",
                json.dumps(event.__dict__, default=str),
            )
            return
        if control == ControlEvent.ELK:
            # ELK Control Event
            _LOGGER.debug(
                "ELK Control Event: %s",
                json.dumps(event.__dict__, default=str),
            )
            return
        if control == ControlEvent.Z_WAVE:
            # Z-Wave Control Event
            _LOGGER.debug(
                "Z-Wave Control Event: %s",
                json.dumps(event.__dict__, default=str),
            )
            return
        if control == ControlEvent.BILLING:
            # Billing Control Event
            _LOGGER.debug(
                "Billing Control Event: %s",
                json.dumps(event.event_info, default=str),
            )
            return
        if control == ControlEvent.PORTAL:
            # Portal Control Event
            self.isy.diagnostics.portal_status = cast(dict, event.event_info)[
                "portal_status"
            ]
            _LOGGER.debug(
                "Portal Control Event: %s",
                json.dumps(self.isy.diagnostics.portal_status, default=str),
            )
            return
        if control == ControlEvent.ZMATTER_Z_WAVE:
            # ZMatter Z-Wave Control Event
            if event.action == "7.1":
                self.isy.diagnostics.zmatter = cast(dict, event.event_info)
            _LOGGER.debug(
                "ZMatter Z-Wave Control Event: action=%s %s",
                event.action,
                json.dumps(self.isy.diagnostics.zmatter, default=str),
            )
            return

        # Unknown Control Event
        try:
            event_name = ControlEvent(control).name
        except ValueError:
            event_name = control
        _LOGGER.debug(
            "Other Control Event: %s %s",
            event_name,
            json.dumps(event.__dict__, default=str),
        )
