"""Message EventRouter for ISY Event Stream Messages."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from typing import TYPE_CHECKING, Any, cast

from pyisy.exceptions import ISYResponseParseError
from pyisy.helpers.xml import parse_xml
from pyisy.logging import LOG_VERBOSE

if TYPE_CHECKING:
    from pyisy.events.tcpsocket import EventStream
    from pyisy.events.websocket import WebSocketClient
    from pyisy.isy import ISY

_LOGGER = logging.getLogger(__name__)


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
            except (KeyError, ValueError):
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
        if control == "_0" and event.action is not None:  # ISY HEARTBEAT
            self.events.heartbeat(int(cast(str, event.action)))
        # elif control == PROP_STATUS:  # NODE UPDATE
        #     self.isy.nodes.update_received(xmldoc)
        # elif control[0] != "_":  # NODE CONTROL EVENT
        #     self.isy.nodes.control_message_received(xmldoc)
        elif control == "_1":  # Trigger Update
            if event.action == "0":
                # Event Status
                if self.isy.programs.loaded:
                    await self.isy.programs.update_received(event)
            if event.action == "1":
                # Get Status (subscribers should refresh)

                return  # FUTURE: Call Node Status refresh
            if event.action == "2":
                # Key Changed (node = key)
                return  # FUTURE: Handle on event bus
            if event.action in {"3", "4"}:  # Info string, IR Learn mode
                return
            if event.action == "5":
                # Schedule status changed (node=key)
                return
            if event.action == "6":
                # Variable status changed
                if self.isy.variables.loaded:
                    # <eventInfo>
                    # <var id="<var-id>" type ="<var-type>">
                    # <val>value</val>
                    # <ts>YYYYMDD HH:MM:SS</ts>
                    # </var>
                    # </eventInfo>
                    await self.isy.variables.update_received(event)
            if event.action == "7":
                # Variable init value set
                if self.isy.variables.loaded:
                    # <eventInfo>
                    # <var id="<var-id>" type ="<var-type>">
                    # <init>value</init>
                    # </var>
                    # </eventInfo>
                    await self.isy.variables.update_received(event, init=True)
            if event.action == "8":
                # Key (event_info = key)
                self.key = cast(str, event.event_info)
                _LOGGER.debug("Key received: %s", self.key)
        elif control == "_2":
            # Driver specific events
            _LOGGER.debug(
                "Event: %s",
                json.dumps(event.__dict__, default=str),
            )

        #     if f"<{ATTR_VAR}" in msg:  # VARIABLE (action=6 or 7)
        #

        #     elif f"<{TAG_NODE}>" in msg and "[" in msg:  # Node Server Update
        #         pass  # This is most likely a duplicate node update.
        #     elif f"<{ATTR_ACTION}>" in msg:
        #         action = value_from_xml(xmldoc, ATTR_ACTION)
        #         if action == ACTION_KEY:
        #             self._program_key = value_from_xml(xmldoc, TAG_EVENT_INFO)
        #             return
        #         if action == ACTION_KEY_CHANGED:
        #             self._program_key = value_from_xml(xmldoc, TAG_NODE)
        #         # Need to reload programs
        #         await self.isy.programs.update()
        elif control == "_3":
            # Node Changed/Updated
            # self.isy.nodes.node_changed_received(event)
            pass
        elif control == "_4":
            # System Configuration Updated
            pass
            # action = "0" -> Time Changed
            # action = "1" -> Time Configuration Changed
            # action = "2" -> NTP Settings Updated
            # action = "3" -> Notifications Settings Updated
            # action = "4" -> NTP Communications Error
            # action = "5" -> Batch Mode Updated
            # node = null
            # <eventInfo>
            # <status>"1"|"0"</status>
            # </eventInfo>
            # action = "6" -> Battery Mode Programming Updated
            # node = null
            # <eventInfo>
            # <status>"1"|"0"</status>
            # </eventInfo>

        elif control == "_5":
            # System Status Changed
            self.isy.system_status_changed_received(event.action)

        elif control == "_7":
            # Progress report, device programming event
            self.isy.nodes.progress_report_received(event)


# 8.5.10 Security System Event (control = “_8”)
# node = null
# eventInfo = null
# action = “0” -> Disconnected
# action = “1” -> Connected
# action = “DA” -> Disarmed
# action = “AW” -> Armed Away
# action = “AS” -> Armed Stay
# action = “ASI” -> Armed Stay Instant
# action = “AN” -> Armed Night
# action = “ANI” -> Armed Night Instant
# Page | 251
# action = “AV” -> Armed Vacation
# 8.5.11 System Alert Event (control = “_9”)
# Not implemented and should be ignore
# OpenADR and Flex Your Power Events (control = “_10”)
# Climate Events (control = “_11”)
#         # _LOGGER.info(
#         #     "Event: %s",
#         #     json.dumps(event.__dict__, indent=4, default=str),
#         # )
# Z-Wave Events (control = “_21”) zwobjs.xsd
