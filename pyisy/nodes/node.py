"""Representation of a node from an ISY."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

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
    INSTEON_TYPE_LOCK,
    INSTEON_TYPE_THERMOSTAT,
    METHOD_SET,
    PROP_ON_LEVEL,
    PROP_RAMP_RATE,
    PROP_SETPOINT_COOL,
    PROP_SETPOINT_HEAT,
    PROP_STATUS,
    PROP_ZWAVE_PREFIX,
    TAG_CONFIG,
    UOM_CLIMATE_MODES,
    UOM_FAN_MODES,
    UOM_TO_STATES,
    URL_CONFIG,
    URL_NODE,
    URL_QUERY,
    URL_ZMATTER_ZWAVE,
    URL_ZWAVE,
    ZWAVE_CAT_DIMMABLE,
    ZWAVE_CAT_LOCK,
    ZWAVE_CAT_THERMOSTAT,
    NodeFamily,
    Protocol,
)
from pyisy.helpers.entity import Entity, EntityStatus, StatusT
from pyisy.helpers.events import EventEmitter
from pyisy.helpers.models import NodeProperty, ZWaveParameter, ZWaveProperties
from pyisy.helpers.xml import parse_xml
from pyisy.logging import _LOGGER
from pyisy.node_servers import NodeServerNodeDef, NodeServers
from pyisy.nodes.nodebase import NodeBase, NodeBaseDetail

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
    prop: dict = field(default_factory=dict)
    rpnode: str = ""
    sgid: str = ""
    custom: dict = field(default_factory=dict)
    devtype: dict = field(default_factory=dict)
    zwave_props: ZWaveProperties | None = field(init=False, default=None)
    protocol: Protocol = Protocol.INSTEON
    node_server: str = ""

    # UPB-only or normally-unused fields, left to avoid errors if used
    qry: str | None = None
    ctl: str | None = None
    rsp: dict | None = None
    tx: str = ""
    rx: str = ""

    def __post_init__(self) -> None:
        """Post-initialization of Node detail dataclass."""
        if self.devtype:
            self.zwave_props = ZWaveProperties(**self.devtype)


class Node(NodeBase, Entity[NodeDetail, StatusT]):
    """This class handles ISY nodes."""

    _parent_node: str | None
    control_events: EventEmitter
    _uom: str = ""
    _precision: int = 0
    _formatted: str = ""
    _is_battery_node: bool = False
    state_set: bool = False

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
        super().__init__(platform=platform, address=address, name=name, detail=detail)
        self._parent_node = detail.pnode if detail.pnode != address else None
        self._protocol = detail.protocol
        self._enabled = detail.enabled
        self.control_events = EventEmitter()
        if detail.prop and PROP_STATUS in detail.prop:
            self.state_set = True
            self._is_battery_node = False
            self.update_state(NodeProperty(**detail.prop))

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
        return self._is_battery_node

    @is_battery_node.setter
    def is_battery_node(self, value: bool) -> None:
        """Override automatic detection of battery node."""
        self._is_battery_node = value

    @property
    def is_backlight_supported(self) -> bool:
        """Confirm if this node supports setting backlight."""
        return (
            (self.protocol == Protocol.INSTEON)
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
                self._protocol == Protocol.INSTEON
                and self.type_
                and any({self.type_.startswith(t) for t in INSTEON_TYPE_DIMMABLE})
                and self.address.endswith(INSTEON_SUBNODE_DIMMABLE)
            )
            or (
                self._protocol == Protocol.ZWAVE
                and self.zwave_props is not None
                and self.zwave_props.category in ZWAVE_CAT_DIMMABLE
            )
        )
        return dimmable

    @property
    def is_lock(self) -> bool:
        """Determine if this device is a door lock type."""
        return (
            self.type_ and any({self.type_.startswith(t) for t in INSTEON_TYPE_LOCK})
        ) or (
            self.protocol == Protocol.ZWAVE
            and self.zwave_props is not None
            and self.zwave_props.category in ZWAVE_CAT_LOCK
        )

    @property
    def is_thermostat(self) -> bool:
        """Determine if this device is a thermostat/climate control device."""
        return (
            self.type_
            and any({self.type_.startswith(t) for t in INSTEON_TYPE_THERMOSTAT})
        ) or (
            self._protocol == Protocol.ZWAVE
            and self.zwave_props is not None
            and self.zwave_props.category in ZWAVE_CAT_THERMOSTAT
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
            return self.platform.entities.get(self._parent_node)
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

    def update_state(self, state: NodeProperty) -> None:
        """Update the various state properties when received."""
        changed = []
        self._last_update = datetime.now()

        if self._is_battery_node and state.control == PROP_STATUS:
            self.state_set = True
            self._is_battery_node = False

        if state.value != self.status:
            changed.append("state")

        if state.formatted not in (self._formatted, ""):
            self._formatted = state.formatted
            changed.append("formatted")

        if state.precision != self._precision:
            self._precision = state.precision
            changed.append("precision")

        if state.uom not in (self._uom, ""):
            self._uom = state.uom
            changed.append("uom")

        if changed:
            self.update_status(int(state.value) if state.value is not None else None)
            _LOGGER.debug(
                "Updated node state: %s (%s), changed=%s",
                self.name,
                self.address,
                ", ".join(changed),
            )
            return

    async def get_zwave_parameter(self, parameter: int) -> ZWaveParameter | None:
        """Retrieve a Z-Wave Parameter from the ISY."""

        if self.protocol != Protocol.ZWAVE:
            _LOGGER.warning("Cannot retrieve parameters of non-Z-Wave device")
            return None

        # /rest/zwave/node/<nodeAddress>/config/query/<parameterNumber>
        # returns something like:
        # <config paramNum="2" size="1" value="80"/>
        # parsed into:
        # {'config': {'param_num': '2', 'size': '1', 'value': '80'}}
        parameter_xml = await self.isy.conn.request(
            self.isy.conn.compile_url(
                [
                    URL_ZMATTER_ZWAVE
                    if self.detail.family == NodeFamily.ZMATTER_ZWAVE
                    else URL_ZWAVE,
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

        parameter_dict: dict[str, Any] = parse_xml(parameter_xml)
        if not (config := parameter_dict[TAG_CONFIG]):
            _LOGGER.warning("Error fetching parameter from ISY")
            return None

        result = ZWaveParameter(**config)

        # Add/update the aux_properties to include the parameter.
        node_prop = NodeProperty(
            control=f"{PROP_ZWAVE_PREFIX}{parameter}",
            value=cast(int, result.value),
            uom=f"{PROP_ZWAVE_PREFIX}{result.size}",
            address=self.address,
        )
        self.update_property(node_prop)

        return result

    async def set_zwave_parameter(
        self, parameter: int, value: int | str, size: int
    ) -> bool:
        """Set a Z-Wave Parameter on an end device via the ISY."""
        if self.protocol != Protocol.ZWAVE:
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
                URL_ZMATTER_ZWAVE
                if self.detail.family == NodeFamily.ZMATTER_ZWAVE
                else URL_ZWAVE,
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
                "Could not set parameter %s on %s.",
                parameter,
                self.address,
            )
            return False
        _LOGGER.debug("Set parameter %s sent to %s.", parameter, self.address)

        # Add/update the aux_properties to include the parameter.
        node_prop = NodeProperty(
            control=f"{PROP_ZWAVE_PREFIX}{parameter}",
            value=int(value),
            uom=f"{PROP_ZWAVE_PREFIX}{size}",
            address=self.address,
        )
        self.update_property(node_prop)

        return True

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

    def get_property_uom(self, prop: str) -> str:
        """Get the Unit of Measurement an aux property."""
        if not (aux_property := self.aux_properties.get(prop)):
            raise ValueError(f"Invalid aux property for node {self.address}")
        return str(aux_property.uom)

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
        if self._uom in ("101", "degrees"):
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
            "'%s' is depreciated, use FADE<xx> commands instead", CMD_MANUAL_DIM_BEGIN
        )
        return await self.send_cmd(CMD_MANUAL_DIM_BEGIN)

    async def stop_manual_dimming(self) -> bool:
        """Stop manually dimming  a device."""
        _LOGGER.warning(
            "'%s' is depreciated, use FADE<xx> commands instead", CMD_MANUAL_DIM_STOP
        )
        return await self.send_cmd(CMD_MANUAL_DIM_STOP)

    def get_node_server_def(self) -> NodeServerNodeDef | None:
        """Retrieve the node server information for a node and control."""
        if not (self.protocol == Protocol.NODE_SERVER and self.node_def_id):
            raise ValueError("Not a node server node")

        servers: NodeServers = self.isy.node_servers
        if not servers.loaded or self.node_server not in servers.slots:
            raise ValueError("Node server definitions not loaded")
        if not (profile := servers.profiles.get(self.node_server)) or profile is None:
            _LOGGER.error("Node server profile not found")
            return None
        return profile.get(self.node_def_id)
