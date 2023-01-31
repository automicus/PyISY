"""Base object for nodes and groups."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast
from xml.dom import minidom

from pyisy.constants import (
    CMD_BEEP,
    CMD_BRIGHTEN,
    CMD_DIM,
    CMD_DISABLE,
    CMD_ENABLE,
    CMD_FADE_DOWN,
    CMD_FADE_STOP,
    CMD_FADE_UP,
    CMD_OFF,
    CMD_OFF_FAST,
    CMD_ON,
    CMD_ON_FAST,
    COMMAND_FRIENDLY_NAME,
    METHOD_COMMAND,
    TAG_NAME,
    URL_CHANGE,
    URL_NODES,
    URL_NOTES,
    NodeFamily,
)
from pyisy.helpers.entity import Entity, EntityDetail, EntityStatus
from pyisy.helpers.events import EventEmitter
from pyisy.helpers.models import NodeNotes, NodeProperty, OptionalIntT
from pyisy.helpers.xml import parse_xml
from pyisy.logging import _LOGGER

if TYPE_CHECKING:
    from pyisy.nodes import Nodes


@dataclass
class NodeBaseDetail(EntityDetail):
    """Dataclass to hold entity detail info."""

    status: OptionalIntT = None
    family: NodeFamily | dict[str, str] | str = ""
    flag: int = 0
    node_def_id: str = ""
    address: str = ""
    name: str = ""
    parent: dict[str, str] = field(default_factory=dict)
    pnode: str = ""
    elk_id: str = ""


class NodeBase(Entity[NodeBaseDetail, OptionalIntT]):
    """Base Object for Nodes and Groups/Scenes."""

    has_children = False
    aux_properties: dict[str, NodeProperty] = {}
    platform: Nodes
    notes: NodeNotes | None
    _primary_node: str
    detail: NodeBaseDetail

    def __init__(
        self,
        platform: Nodes,
        address: str,
        name: str,
        detail: NodeBaseDetail,
        aux_properties: dict[str, NodeProperty] | None = None,
    ):
        """Initialize a Node Base class."""
        self.platform = platform
        self.isy = platform.isy
        self._address = address
        self._name = name

        self.aux_properties = aux_properties if aux_properties else {}
        # self._family = family_id
        self.notes = None
        self._primary_node = detail.pnode
        self._status = detail.status
        self.detail = detail
        self._last_update = datetime.now()
        self._last_changed = datetime.now()
        self.status_events = EventEmitter()

    def __str__(self) -> str:
        """Return a string representation of the node."""
        return f"{type(self).__name__}({self.address})"

    @property
    def folder(self) -> str | None:
        """Return the folder of the current node as a property."""
        return self.platform.get_folder(self.address)

    @property
    def primary_node(self) -> str:
        """Return just the parent/primary node address.

        This is similar to Node.parent_node but does not return the whole Node
        class, and will return itself if it is the primary node/group.

        """
        return self._primary_node

    async def get_notes(self) -> None:
        """Retrieve and parse the notes for a given node.

        Notes are not retrieved unless explicitly requested by
        a call to this function.
        """
        notes_xml = await self.isy.conn.request(
            self.isy.conn.compile_url([URL_NODES, self.address, URL_NOTES]), ok404=False
        )
        if notes_xml is None or notes_xml != "" or notes_xml.endswith(" not found"):
            return

        notes_dict: dict[str, Any] = parse_xml(notes_xml)

        if not (notes := notes_dict.get("node_properties")):
            return

        self.notes = NodeNotes(**cast(dict, notes))

    async def update(
        self,
        event: NodeProperty | None = None,
        wait_time: float = 0,
        xmldoc: minidom.Element | None = None,
    ) -> None:
        """Update the group with values from the controller."""
        self.update_last_update()

    def update_property(self, prop: NodeProperty) -> None:
        """Update an aux property for the node when received."""
        self.update_last_update()

        aux_prop = self.aux_properties.get(prop.control)
        if aux_prop:
            if prop.uom == "" and not aux_prop.uom == "":
                # Guard against overwriting known UOM with blank UOM (ISYv4).
                prop.uom = aux_prop.uom
            if aux_prop == prop:
                return
        self.aux_properties[prop.control] = prop
        self.update_last_changed()
        self.status_events.notify(
            EntityStatus(
                self.address, self.status, self._last_changed, self._last_update
            )
        )

    async def send_cmd(
        self,
        cmd: str,
        val: str | int | float | None = None,
        uom: str | None = None,
        query: dict[str, str] | None = None,
    ) -> bool:
        """Send a command to the device."""
        value = str(val) if val is not None else None
        _uom = str(uom) if uom is not None else None
        req = [URL_NODES, str(self.address), METHOD_COMMAND, cmd]
        if value:
            req.append(value)
        if _uom:
            req.append(_uom)
        req_url = self.isy.conn.compile_url(req, query)
        if not await self.isy.conn.request(req_url):
            _LOGGER.warning(
                "Could not send %s command to %s.",
                COMMAND_FRIENDLY_NAME.get(cmd),
                self.address,
            )
            return False
        _LOGGER.debug(
            "Command %s sent to %s.", COMMAND_FRIENDLY_NAME.get(cmd), self.address
        )
        return True

    async def beep(self) -> bool:
        """Identify physical device by sound (if supported)."""
        return await self.send_cmd(CMD_BEEP)

    async def brighten(self) -> bool:
        """Increase brightness of a device by ~3%."""
        return await self.send_cmd(CMD_BRIGHTEN)

    async def dim(self) -> bool:
        """Decrease brightness of a device by ~3%."""
        return await self.send_cmd(CMD_DIM)

    async def disable(self) -> bool:
        """Send command to the node to disable it."""
        if not await self.isy.conn.request(
            self.isy.conn.compile_url([URL_NODES, str(self.address), CMD_DISABLE])
        ):
            _LOGGER.warning("Could not %s %s.", CMD_DISABLE, self.address)
            return False
        return True

    async def enable(self) -> bool:
        """Send command to the node to enable it."""
        if not await self.isy.conn.request(
            self.isy.conn.compile_url([URL_NODES, str(self.address), CMD_ENABLE])
        ):
            _LOGGER.warning("Could not %s %s.", CMD_ENABLE, self.address)
            return False
        return True

    async def fade_down(self) -> bool:
        """Begin fading down (dim) a device."""
        return await self.send_cmd(CMD_FADE_DOWN)

    async def fade_stop(self) -> bool:
        """Stop fading a device."""
        return await self.send_cmd(CMD_FADE_STOP)

    async def fade_up(self) -> bool:
        """Begin fading up (dim) a device."""
        return await self.send_cmd(CMD_FADE_UP)

    async def fast_off(self) -> bool:
        """Start manually brightening a device."""
        return await self.send_cmd(CMD_OFF_FAST)

    async def fast_on(self) -> bool:
        """Start manually brightening a device."""
        return await self.send_cmd(CMD_ON_FAST)

    async def query(self) -> bool:
        """Request the ISY query this node."""
        return await self.isy.query(address=self.address)

    async def turn_off(self) -> bool:
        """Turn off the nodes/group in the ISY."""
        return await self.send_cmd(CMD_OFF)

    async def turn_on(self, val: int | str | None = None) -> bool:
        """
        Turn the node on.

        |  [optional] val: The value brightness value (0-255) for the node.
        """
        if val is None or type(self).__name__ == "Group":
            cmd = CMD_ON
        elif int(val) > 0:
            cmd = CMD_ON
            val = str(val) if int(val) <= 255 else None
        else:
            cmd = CMD_OFF
            val = None
        return await self.send_cmd(cmd, val)

    async def rename(self, new_name: str) -> bool:
        """
        Rename the node or group in the ISY.

        Note: Feature was added in ISY v5.2.0, this will fail on earlier versions.
        """
        # /rest/nodes/<nodeAddress>/change?name=<newName>
        req_url = self.isy.conn.compile_url(
            [URL_NODES, self.address, URL_CHANGE],
            query={TAG_NAME: new_name},
        )
        if not await self.isy.conn.request(req_url):
            _LOGGER.warning(
                "Could not update name for %s.",
                self.address,
            )
            return False
        _LOGGER.debug("Renamed %s to %s.", self.address, new_name)

        self._name = new_name
        return True
