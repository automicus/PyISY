"""Representation of a node from an ISY."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING
from xml.dom import minidom

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Generic
from pyisy.constants import (
    BACKLIGHT_SUPPORT,
    CLIMATE_SETPOINT_MIN_GAP,
    CMD_CLIMATE_FAN_SETTING,
    CMD_CLIMATE_MODE,
    CMD_MANUAL_DIM_BEGIN,
    CMD_MANUAL_DIM_STOP,
    CMD_SECURE,
    INSTEON_SUBNODE_DIMMABLE,
    INSTEON_TYPE_DIMMABLE,
    PROTO_NODE_SERVER,
    INSTEON_TYPE_LOCK,
    INSTEON_TYPE_THERMOSTAT,
    METHOD_SET,
    PROP_ON_LEVEL,
    PROP_RAMP_RATE,
    PROP_SETPOINT_COOL,
    PROP_SETPOINT_HEAT,
    PROP_STATUS,
    PROP_ZWAVE_PREFIX,
    PROTO_INSTEON,
    PROTO_ZWAVE,
    TAG_CONFIG,
    TAG_GROUP,
    TAG_PARAMETER,
    TAG_SIZE,
    TAG_VALUE,
    UOM_CLIMATE_MODES,
    UOM_FAN_MODES,
    UOM_TO_STATES,
    URL_CONFIG,
    URL_GET,
    URL_NODE,
    URL_NODES,
    URL_QUERY,
    URL_ZWAVE,
    ZWAVE_CAT_DIMMABLE,
    ZWAVE_CAT_LOCK,
    ZWAVE_CAT_THERMOSTAT,
)
from pyisy.exceptions import XML_ERRORS, XML_PARSE_ERROR, ISYResponseParseError
from pyisy.helpers.events import EventEmitter
from pyisy.helpers.entity import Entity, EntityStatus
from pyisy.helpers.models import NodeProperty, ZWaveProperties
from pyisy.helpers.xml import attr_from_xml
from pyisy.logging import _LOGGER
from pyisy.nodes.group import Group
from pyisy.nodes.nodebase import NodeBase, NodeBaseDetail
from pyisy.nodes.parser import parse_xml_properties

if TYPE_CHECKING:
    from pyisy.nodes import Nodes


@dataclass
class VariableStatus(EntityStatus):
    """Dataclass to hold variable status."""

    timestamp: datetime
    precision: int = 0


@dataclass
class NodeDetail(NodeBaseDetail):
    """Dataclass to hold entity detail info."""

    type_: str = ""
    enabled: bool = True
    device_class: str = "0"
    wattage: str = "0"
    dc_period: str = "0"
    start_delay: str = "0"
    end_delay: str = "0"
    prop: dict[str, str] = field(default_factory=dict)
    rpnode: str = ""
    sgid: str = ""
    custom: dict[str, str] = field(default_factory=dict)
    devtype: dict[str, str] = field(default_factory=dict)
    zwave_props: ZWaveProperties = field(init=False)
    is_battery_node: bool = field(init=False)
    protocol: str = PROTO_INSTEON
    node_server: str = ""

    def __post_init__(self) -> None:
        """Post-initialization of Node detail dataclass."""
        if self.devtype:
            self.zwave_props = ZWaveProperties(**self.devtype)
        if not self.prop:
            self.is_battery_node = True
        if self.protocol.startswith(f"{PROTO_NODE_SERVER}_"):
            _, _, self.node_server = self.protocol.rpartition("_")


class Node(NodeBase, Entity):
    """This class handles ISY nodes."""

    _parent_node: str | None
    control_events: EventEmitter
    _uom: str = ""
    _precision: int = 0
    _formatted: str = ""

    detail: NodeDetail
    platform: Nodes

    def __init__(
        self,
        platform: Nodes,
        address: str,
        name: str,
        detail: NodeDetail,
    ):
        """Initialize a Node class."""
        self._parent_node = detail.pnode if detail.pnode != address else None
        self._protocol = detail.protocol
        self.control_events = EventEmitter()
        # self.is_battery_node = not state_set # TODO correct this on status load

        super().__init__(platform=platform, address=address, name=name, detail=detail)

    @property
    def enabled(self) -> bool:
        """Return if the device is enabled or not in the ISY."""
        return self.enabled

    @property
    def formatted(self) -> str:
        """Return the formatted value with units, if provided."""
        return self._formatted

    @property
    def is_battery_node(self) -> bool:
        """
        Confirm if this is a battery node or a normal node.

        Battery nodes do not provide a 'ST' property, only 'BATLVL'.
        """
        return self.detail.is_battery_node

    @property
    def is_backlight_supported(self) -> bool:
        """Confirm if this node supports setting backlight."""
        return (
            (self.protocol == PROTO_INSTEON)
            and self.node_def_id is not None
            and (self.node_def_id in BACKLIGHT_SUPPORT)
        )

    @property
    def is_dimmable(self) -> bool:
        """
        Return the best guess if this is a dimmable node.

        Check ISYv4 UOM, then Insteon and Z-Wave Types for dimmable types.
        """
        dimmable = (
            "%" in str(self._uom)
            or (
                self._protocol == PROTO_INSTEON
                and self.type_
                and any({self.type_.startswith(t) for t in INSTEON_TYPE_DIMMABLE})
                and self.address.endswith(INSTEON_SUBNODE_DIMMABLE)
            )
            or (
                self._protocol == PROTO_ZWAVE
                and self.zwave_props is not None
                and self.zwave_props.cat in ZWAVE_CAT_DIMMABLE
            )
        )
        return dimmable

    @property
    def is_lock(self) -> bool:
        """Determine if this device is a door lock type."""
        return (
            self.type_ and any({self.type_.startswith(t) for t in INSTEON_TYPE_LOCK})
        ) or (
            self.protocol == PROTO_ZWAVE
            and self.zwave_props is not None
            and self.zwave_props.cat in ZWAVE_CAT_LOCK
        )

    @property
    def is_thermostat(self) -> bool:
        """Determine if this device is a thermostat/climate control device."""
        return (
            self.type_
            and any({self.type_.startswith(t) for t in INSTEON_TYPE_THERMOSTAT})
        ) or (
            self._protocol == PROTO_ZWAVE
            and self.zwave_props is not None
            and self.zwave_props.cat in ZWAVE_CAT_THERMOSTAT
        )

    @property
    def node_def_id(self) -> str | None:
        """Return the node definition id (used for ISYv5)."""
        return self.detail.node_def_id

    @property
    def node_server(self) -> str | None:
        """Return the node server parent slot (used for v5 Node Server devices)."""
        return self.detail.node_server

    @property
    def parent_node(self) -> Entity | None:
        """
        Return the parent node object of this node.

        Typically this is for devices that are represented as multiple nodes in
        the ISY, such as door and leak sensors.
        Return None if there is no parent.

        """
        if self._parent_node:
            return self.platform.get_by_id(self._parent_node)
        return None

    @property
    def precision(self) -> int:
        """Return the precision of the raw device value."""
        return self._precision

    @property
    def type_(self) -> str:
        """Return the device typecode (Used for Insteon)."""
        return self.detail.type_

    @property
    def uom(self) -> str | list:
        """Return the unit of measurement for the device."""
        return self._uom

    @property
    def zwave_props(self) -> ZWaveProperties | None:
        """Return the Z-Wave Properties (used for Z-Wave devices)."""
        return self.detail.zwave_props

    async def get_zwave_parameter(self, parameter: int) -> dict | None:
        """Retrieve a Z-Wave Parameter from the ISY."""

        if self.protocol != PROTO_ZWAVE:
            _LOGGER.warning("Cannot retrieve parameters of non-Z-Wave device")
            return None

        # /rest/zwave/node/<nodeAddress>/config/query/<parameterNumber>
        # returns something like:
        # <config paramNum="2" size="1" value="80"/>
        parameter_xml = await self.isy.conn.request(
            self.isy.conn.compile_url(
                [
                    URL_ZWAVE,
                    URL_NODE,
                    self.address,
                    URL_CONFIG,
                    URL_QUERY,
                    str(parameter),
                ]
            )
        )

        if parameter_xml is None or parameter_xml == "":
            _LOGGER.warning("Error fetching parameter from ISY")
            return None

        try:
            parameter_dom = minidom.parseString(parameter_xml)
            # TODO: Using old parser
        except XML_ERRORS as exc:
            _LOGGER.error("%s: Node Parameter %s", XML_PARSE_ERROR, parameter_xml)
            raise ISYResponseParseError() from exc

        size = int(attr_from_xml(parameter_dom, TAG_CONFIG, TAG_SIZE))
        value = int(attr_from_xml(parameter_dom, TAG_CONFIG, TAG_VALUE))

        # Add/update the aux_properties to include the parameter.
        node_prop = NodeProperty(
            control=f"{PROP_ZWAVE_PREFIX}{parameter}",
            value=value,
            uom=f"{PROP_ZWAVE_PREFIX}{size}",
            address=self.address,
        )
        self.update_property(node_prop)

        return {TAG_PARAMETER: parameter, TAG_SIZE: size, TAG_VALUE: value}

    async def set_zwave_parameter(
        self, parameter: int, value: int | str, size: int
    ) -> bool:
        """Set a Z-Wave Parameter on an end device via the ISY."""

        if self.protocol != PROTO_ZWAVE:
            _LOGGER.warning("Cannot set parameters of non-Z-Wave device")
            return False

        try:
            int(parameter)
        except ValueError:
            _LOGGER.error("Parameter must be an integer")
            return False

        if int(size) not in [1, 2, 4]:
            _LOGGER.error("Size must either 1, 2, or 4 (bytes)")
            return False

        if str(value).startswith("0x"):
            try:
                int(str(value), base=16)
            except ValueError:
                _LOGGER.error("Value must be valid hex byte string or integer.")
                return False
        else:
            try:
                int(value)
            except ValueError:
                _LOGGER.error("Value must be valid hex byte string or integer.")
                return False

        # /rest/zwave/node/<nodeAddress>/config/set/<parameterNumber>/<value>/<size>
        req_url = self.isy.conn.compile_url(
            [
                URL_ZWAVE,
                URL_NODE,
                self.address,
                URL_CONFIG,
                METHOD_SET,
                str(parameter),
                str(value),
                str(size),
            ]
        )
        if not await self.isy.conn.request(req_url):
            _LOGGER.warning(
                "ISY could not set parameter %s on %s.",
                parameter,
                self.address,
            )
            return False
        _LOGGER.debug("ISY set parameter %s sent to %s.", parameter, self.address)

        # Add/update the aux_properties to include the parameter.
        node_prop = NodeProperty(
            control=f"{PROP_ZWAVE_PREFIX}{parameter}",
            value=int(value),
            uom=f"{PROP_ZWAVE_PREFIX}{size}",
            address=self.address,
        )
        self.update_property(node_prop)

        return True

    # async def update(
    #     self,
    #     event: NodeProperty | None = None,
    #     wait_time: float = 0,
    #     xmldoc: minidom.Element | None = None,
    # ) -> None:
    #     """Update the value of the node from the controller."""
    #     if not self.isy.auto_update and not xmldoc:
    #         await asyncio.sleep(wait_time)
    #         req_url = self.isy.conn.compile_url(
    #             [URL_NODES, self.address, URL_GET, PROP_STATUS]
    #         )
    #         xml = await self.isy.conn.request(req_url)
    #         try:
    #             xmldoc = minidom.parseString(xml)
    #         except XML_ERRORS as exc:
    #             _LOGGER.error("%s: Nodes", XML_PARSE_ERROR)
    #             raise ISYResponseParseError(XML_PARSE_ERROR) from exc

    #     if xmldoc is None:
    #         _LOGGER.warning("ISY could not update node: %s", self.address)
    #         return

    #     self._last_update = datetime.now()
    #     state, aux_props, _ = parse_xml_properties(xmldoc)
    #     self._aux_properties.update(aux_props)
    #     self.update_state(state)
    #     _LOGGER.debug("ISY updated node: %s", self.address)

    def update_state(self, state: NodeProperty) -> None:
        """Update the various state properties when received."""
        changed = False
        self._last_update = datetime.now()

        if state.precision != self._precision:
            self._precision = state.precision
            changed = True

        if state.uom not in (self._uom, ""):
            self._uom = state.uom
            changed = True

        if state.formatted is not None and state.formatted != self._formatted:
            self._formatted = state.formatted
            changed = True

        if state.value != self.status or changed:
            self.update_status(state.value)
            return

    def get_command_value(self, uom: str, cmd: str) -> str | None:
        """Check against the list of UOM States if this is a valid command."""
        if cmd not in UOM_TO_STATES[uom].values():
            _LOGGER.warning(
                "Failed to call %s on %s, invalid command.", cmd, self.address
            )
            return None
        return list(UOM_TO_STATES[uom].keys())[
            list(UOM_TO_STATES[uom].values()).index(cmd)
        ]

    def get_groups(self, controller: bool = True, responder: bool = True) -> list[str]:
        """
        Return the groups (scenes) of which this node is a member.

        If controller is True, then the scene it controls is added to the list
        If responder is True, then the scenes it is a responder of are added to
        the list.
        """
        groups = []
        # TODO: Not Done
        for child in self.platform.all_lower_nodes:
            if child[0] == TAG_GROUP:
                if responder:
                    if self.address in self.platform[child[2]].members:
                        groups.append(child[2])
                elif controller:
                    if self.address in self.platform[child[2]].controllers:
                        groups.append(child[2])
        return groups

    def get_property_uom(self, prop: str) -> str | list | None:
        """Get the Unit of Measurement an aux property."""
        if aux_property := self.aux_properties.get(prop):
            return aux_property.uom
        return None

    async def secure_lock(self) -> bool:
        """Send a command to securely lock a lock device."""
        if not self.is_lock:
            _LOGGER.warning("Failed to lock %s, it is not a lock node.", self.address)
            return False
        return await self.send_cmd(CMD_SECURE, "1")

    async def secure_unlock(self) -> bool:
        """Send a command to securely lock a lock device."""
        if not self.is_lock:
            _LOGGER.warning("Failed to unlock %s, it is not a lock node.", self.address)
            return False
        return await self.send_cmd(CMD_SECURE, "0")

    async def set_climate_mode(self, cmd: str) -> bool:
        """Send a command to the device to set the climate mode."""
        if not self.is_thermostat:
            _LOGGER.warning(
                "Failed to set setpoint on %s, it is not a thermostat node.",
                self.address,
            )
        if cmd_value := self.get_command_value(UOM_CLIMATE_MODES, cmd):
            return await self.send_cmd(CMD_CLIMATE_MODE, cmd_value)
        return False

    async def set_climate_setpoint(self, val: int) -> bool:
        """Send a command to the device to set the system setpoints."""
        if not self.is_thermostat:
            _LOGGER.warning(
                "Failed to set setpoint on %s, it is not a thermostat node.",
                self.address,
            )
            return False
        adjustment = int(CLIMATE_SETPOINT_MIN_GAP / 2.0)

        commands = [
            self.set_climate_setpoint_heat(val - adjustment),
            self.set_climate_setpoint_cool(val + adjustment),
        ]
        result = await asyncio.gather(*commands, return_exceptions=True)
        return all(result)

    async def set_climate_setpoint_heat(self, val: int) -> bool:
        """Send a command to the device to set the system heat setpoint."""
        return await self._set_climate_setpoint(val, "heat", PROP_SETPOINT_HEAT)

    async def set_climate_setpoint_cool(self, val: int) -> bool:
        """Send a command to the device to set the system heat setpoint."""
        return await self._set_climate_setpoint(val, "cool", PROP_SETPOINT_COOL)

    async def _set_climate_setpoint(
        self, val: int, setpoint_name: str, setpoint_prop: str
    ) -> bool:
        """Send a command to the device to set the system heat setpoint."""
        if not self.is_thermostat:
            _LOGGER.warning(
                "Failed to set %s setpoint on %s, it is not a thermostat node.",
                setpoint_name,
                self.address,
            )
            return False
        # ISY wants 2 times the temperature for Insteon in order to not lose precision
        if self._uom in ["101", "degrees"]:
            val = 2 * val
        return await self.send_cmd(
            setpoint_prop, str(val), self.get_property_uom(setpoint_prop)
        )

    async def set_fan_mode(self, cmd: str) -> bool:
        """Send a command to the device to set the fan mode setting."""
        cmd_value = self.get_command_value(UOM_FAN_MODES, cmd)
        if cmd_value:
            return await self.send_cmd(CMD_CLIMATE_FAN_SETTING, cmd_value)
        return False

    async def set_on_level(self, val: int | str) -> bool:
        """Set the ON Level for a device."""
        if not val or int(val) not in range(256):
            _LOGGER.warning(
                "Invalid value for On Level for %s. Valid values are 0-255.",
                self.address,
            )
            return False
        return await self.send_cmd(PROP_ON_LEVEL, str(val))

    async def set_ramp_rate(self, val: int | str) -> bool:
        """Set the Ramp Rate for a device."""
        if not val or int(val) not in range(32):
            _LOGGER.warning(
                "Invalid value for Ramp Rate for %s. "
                "Valid values are 0-31. See 'INSTEON_RAMP_RATES' in constants.py for values.",
                self.address,
            )
            return False
        return await self.send_cmd(PROP_RAMP_RATE, str(val))

    async def start_manual_dimming(self) -> bool:
        """Begin manually dimming a device."""
        _LOGGER.warning(
            "'%s' is depreciated, use FADE__ commands instead", CMD_MANUAL_DIM_BEGIN
        )
        return await self.send_cmd(CMD_MANUAL_DIM_BEGIN)

    async def stop_manual_dimming(self) -> bool:
        """Stop manually dimming  a device."""
        _LOGGER.warning(
            "'%s' is depreciated, use FADE__ commands instead", CMD_MANUAL_DIM_STOP
        )
        return await self.send_cmd(CMD_MANUAL_DIM_STOP)
