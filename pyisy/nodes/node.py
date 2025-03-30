"""Representation of a node from an ISY."""

from __future__ import annotations

import asyncio
from math import isnan
from typing import TYPE_CHECKING
from xml.dom import minidom

from ..constants import (
    BACKLIGHT_SUPPORT,
    CLIMATE_SETPOINT_MIN_GAP,
    CMD_CLIMATE_FAN_SETTING,
    CMD_CLIMATE_MODE,
    CMD_MANUAL_DIM_BEGIN,
    CMD_MANUAL_DIM_STOP,
    CMD_SECURE,
    FAMILY_ZMATTER_ZWAVE,
    INSTEON_SUBNODE_DIMMABLE,
    INSTEON_TYPE_DIMMABLE_TUP,
    INSTEON_TYPE_LOCK_TUP,
    INSTEON_TYPE_THERMOSTAT_TUP,
    METHOD_GET,
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
    URL_NODE,
    URL_NODES,
    URL_QUERY,
    URL_ZMATTER_ZWAVE,
    URL_ZWAVE,
    ZWAVE_CAT_DIMMABLE,
    ZWAVE_CAT_LOCK,
    ZWAVE_CAT_THERMOSTAT,
)
from ..exceptions import XML_ERRORS, XML_PARSE_ERROR, ISYResponseParseError
from ..helpers import (
    EventEmitter,
    NodeProperty,
    ZWaveProperties,
    attr_from_xml,
    now,
    parse_xml_properties,
)
from ..logging import _LOGGER
from .nodebase import NodeBase

if TYPE_CHECKING:
    from . import Nodes


class Node(NodeBase):
    """
    This class handles ISY nodes.

    |  parent: The node manager object.
    |  address: The Node ID.
    |  value: The current Node value.
    |  name: The node name.
    |  spoken: The string of the Notes Spoken field.
    |  notes: Notes from the ISY
    |  uom: Unit of Measure returned by the ISY
    |  prec: Precision of the Node (10^-prec)
    |  aux_properties: Additional Properties for the node
    |  zwave_props: Z-Wave Properties from the devtype tag (used for Z-Wave Nodes.)
    |  node_def_id: Node Definition ID (used for ISY firmwares >=v5)
    |  pnode: Node ID of the primary node
    |  device_type: device type.
    |  node_server: the parent node server slot used
    |  protocol: the device protocol used (z-wave, zigbee, insteon, node server)

    :ivar status: A watched property that indicates the current status of the
                  node.
    :ivar has_children: Property indicating that there are no more children.
    """

    def __init__(
        self,
        nodes: Nodes,
        address: str,
        name: str,
        state: NodeProperty,
        aux_properties: dict[str, NodeProperty] | None = None,
        zwave_props: ZWaveProperties | None = None,
        node_def_id: str | None = None,
        pnode: str | None = None,
        device_type: str | None = None,
        enabled: bool | None = None,
        node_server: object | None = None,
        protocol: str | None = None,
        family_id: str | None = None,
        state_set: bool = True,
        flag: int = 0,
    ) -> None:
        """Initialize a Node class."""
        self._enabled = enabled if enabled is not None else True
        self._formatted = state.formatted
        self._node_def_id = node_def_id
        self._node_server = node_server
        self._parent_node = pnode if pnode != address else None
        self._prec = state.prec
        self._protocol = protocol
        self._type = device_type
        self._uom = state.uom
        self._zwave_props = zwave_props
        self.control_events = EventEmitter()
        self._is_battery_node = not state_set
        super().__init__(
            nodes,
            address,
            name,
            state.value,
            family_id=family_id,
            aux_properties=aux_properties,
            pnode=pnode,
            flag=flag,
        )

    @property
    def dimmable(self) -> bool:
        """
        Return the best guess if this is a dimmable node.

        DEPRECIATED: USE is_dimmable INSTEAD. Will be removed in future release.
        """
        _LOGGER.info("Node.dimmable is depreciated. Use Node.is_dimmable instead.")
        return self.is_dimmable

    @property
    def enabled(self) -> bool:
        """Return if the device is enabled or not in the ISY."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Set if the device is enabled or not in the ISY."""
        if self._enabled != value:
            self._enabled = value

    @property
    def formatted(self) -> str | None:
        """Return the formatted value with units, if provided."""
        return self._formatted

    @property
    def is_battery_node(self) -> bool:
        """
        Confirm if this is a battery node or a normal node.

        Battery nodes do not provide a 'ST' property, only 'BATLVL'.
        """
        return self._is_battery_node

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
        return (
            "%" in str(self._uom)
            or (
                self._protocol == PROTO_INSTEON
                and self.type
                and self.type.startswith(INSTEON_TYPE_DIMMABLE_TUP)
                and self._id.endswith(INSTEON_SUBNODE_DIMMABLE)
            )
            or (
                self._protocol == PROTO_ZWAVE
                and self._zwave_props is not None
                and self._zwave_props.category in ZWAVE_CAT_DIMMABLE
            )
        )

    @property
    def is_lock(self) -> bool:
        """Determine if this device is a door lock type."""
        return (self.type and self.type.startswith(INSTEON_TYPE_LOCK_TUP)) or (
            self.protocol == PROTO_ZWAVE
            and self.zwave_props.category
            and self.zwave_props.category in ZWAVE_CAT_LOCK
        )

    @property
    def is_thermostat(self) -> bool:
        """Determine if this device is a thermostat/climate control device."""
        return (self.type and self.type.startswith(INSTEON_TYPE_THERMOSTAT_TUP)) or (
            self._protocol == PROTO_ZWAVE
            and self.zwave_props.category
            and self.zwave_props.category in ZWAVE_CAT_THERMOSTAT
        )

    @property
    def node_def_id(self) -> str | None:
        """Return the node definition id (used for ISYv5)."""
        return self._node_def_id

    @property
    def node_server(self) -> object | None:
        """Return the node server parent slot (used for v5 Node Server devices)."""
        return self._node_server

    @property
    def parent_node(self) -> Node | None:
        """
        Return the parent node object of this node.

        Typically this is for devices that are represented as multiple nodes in
        the ISY, such as door and leak sensors.
        Return None if there is no parent.

        """
        if self._parent_node:
            return self._nodes.get_by_id(self._parent_node)
        return None

    @property
    def prec(self) -> int:
        """Return the precision of the raw device value."""
        return self._prec

    @property
    def protocol(self) -> str | None:
        """Return the device standard used (Z-Wave, Zigbee, Insteon, Node Server)."""
        return self._protocol

    @property
    def type(self) -> str | None:
        """Return the device typecode (Used for Insteon)."""
        return self._type

    @property
    def uom(self) -> str | None:
        """Return the unit of measurement for the device."""
        return self._uom

    @property
    def zwave_props(self) -> ZWaveProperties | None:
        """Return the Z-Wave Properties (used for Z-Wave devices)."""
        return self._zwave_props

    async def get_zwave_parameter(self, parameter: int) -> dict[str, str] | bool | None:
        """Retrieve a Z-Wave Parameter from the ISY."""

        if self.protocol != PROTO_ZWAVE:
            _LOGGER.warning("Cannot retrieve parameters of non-Z-Wave device")
            return None

        if not isinstance(parameter, int):
            _LOGGER.error("Parameter must be an integer")
            return None

        # /rest/zwave/node/<nodeAddress>/config/query/<parameterNumber>
        # returns something like:
        # <config paramNum="2" size="1" value="80"/>
        parameter_xml = await self.isy.conn.request(
            self.isy.conn.compile_url(
                [
                    URL_ZMATTER_ZWAVE if self.family == FAMILY_ZMATTER_ZWAVE else URL_ZWAVE,
                    URL_NODE,
                    self._id,
                    URL_CONFIG,
                    URL_QUERY,
                    str(parameter),
                ]
            )
        )

        if parameter_xml is None or parameter_xml == "":
            _LOGGER.warning("Error fetching parameter from ISY")
            return False

        try:
            parameter_dom = minidom.parseString(parameter_xml)
        except XML_ERRORS as exc:
            _LOGGER.error("%s: Node Parameter %s", XML_PARSE_ERROR, parameter_xml)
            raise ISYResponseParseError from exc

        size = int(attr_from_xml(parameter_dom, TAG_CONFIG, TAG_SIZE))
        value = attr_from_xml(parameter_dom, TAG_CONFIG, TAG_VALUE)

        # Add/update the aux_properties to include the parameter.
        node_prop = NodeProperty(
            f"{PROP_ZWAVE_PREFIX}{parameter}",
            value,
            uom=f"{PROP_ZWAVE_PREFIX}{size}",
            address=self._id,
        )
        self.update_property(node_prop)

        return {TAG_PARAMETER: parameter, TAG_SIZE: size, TAG_VALUE: value}

    async def set_zwave_parameter(self, parameter: int, value: int | str, size: int) -> bool:
        """Set a Z-Wave Parameter on an end device via the ISY."""

        if self.protocol != PROTO_ZWAVE:
            _LOGGER.warning("Cannot set parameters of non-Z-Wave device")
            return False

        try:
            int(parameter)
        except ValueError:
            _LOGGER.error("Parameter must be an integer")
            return False

        if size not in [1, "1", 2, "2", 4, "4"]:
            _LOGGER.error("Size must either 1, 2, or 4 (bytes)")
            return False

        if str(value).startswith("0x"):
            try:
                int(value, base=16)
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
                URL_ZMATTER_ZWAVE if self.family == FAMILY_ZMATTER_ZWAVE else URL_ZWAVE,
                URL_NODE,
                self._id,
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
                self._id,
            )
            return False
        _LOGGER.debug("ISY set parameter %s sent to %s.", parameter, self._id)

        # Add/update the aux_properties to include the parameter.
        node_prop = NodeProperty(
            f"{PROP_ZWAVE_PREFIX}{parameter}",
            value,
            uom=f"{PROP_ZWAVE_PREFIX}{size}",
            address=self._id,
        )
        self.update_property(node_prop)

        return True

    async def set_zwave_lock_code(self, user_num: int, code: int) -> bool:
        """Set a Z-Wave Lock User Code via the ISY."""
        if self.protocol != PROTO_ZWAVE:
            raise TypeError("Cannot set parameters of non-Z-Wave device")

        # /rest/zwave/node/<nodeAddress>/security/user/<user_num>/set/code/<code>
        req_url = self.isy.conn.compile_url(
            [
                URL_ZMATTER_ZWAVE if self.family == FAMILY_ZMATTER_ZWAVE else URL_ZWAVE,
                URL_NODE,
                self.address,
                "security",
                "user",
                str(user_num),
                "set/code",
                str(code),
            ]
        )
        if not await self.isy.conn.request(req_url):
            _LOGGER.warning(
                "Could not set user code %s on %s.",
                user_num,
                self.address,
            )
            return False
        _LOGGER.debug("Set user code %s sent to %s.", user_num, self.address)

        return True

    async def delete_zwave_lock_code(self, user_num: int) -> bool:
        """Delete a Z-Wave Lock User Code via the ISY."""
        if self.protocol != PROTO_ZWAVE:
            raise TypeError("Cannot set parameters of non-Z-Wave device")

        # /rest/zwave/node/<nodeAddress>/security/user/<user_num>/delete
        req_url = self.isy.conn.compile_url(
            [
                URL_ZMATTER_ZWAVE if self.family == FAMILY_ZMATTER_ZWAVE else URL_ZWAVE,
                URL_NODE,
                self.address,
                "security",
                "user",
                str(user_num),
                "delete",
            ]
        )
        if not await self.isy.conn.request(req_url):
            _LOGGER.warning(
                "Could not delete user code %s on %s.",
                user_num,
                self.address,
            )
            return False
        _LOGGER.debug("Deleted user code %s sent to %s.", user_num, self.address)

        return True

    async def update(self, event=None, wait_time: int = 0, xmldoc: minidom.Document | None = None) -> None:
        """Update the value of the node from the controller."""
        if not self.isy.auto_update and not xmldoc:
            await asyncio.sleep(wait_time)
            req_url = self.isy.conn.compile_url([URL_NODES, self._id, METHOD_GET, PROP_STATUS])
            xml = await self.isy.conn.request(req_url)
            try:
                xmldoc = minidom.parseString(xml)
            except XML_ERRORS as exc:
                _LOGGER.error("%s: Nodes", XML_PARSE_ERROR)
                raise ISYResponseParseError(XML_PARSE_ERROR) from exc

        if xmldoc is None:
            _LOGGER.warning("ISY could not update node: %s", self._id)
            return

        self._last_update = now()
        state, aux_props, _ = parse_xml_properties(xmldoc)
        self._aux_properties.update(aux_props)
        self.update_state(state)
        _LOGGER.debug("ISY updated node: %s", self._id)

    def update_state(self, state: NodeProperty) -> None:
        """Update the various state properties when received."""
        if not isinstance(state, NodeProperty):
            _LOGGER.error("Could not update state values. Invalid type provided.")
            return
        changed = False
        self._last_update = now()

        if state.prec != self._prec:
            self._prec = state.prec
            changed = True

        if state.uom not in (self._uom, ""):
            self._uom = state.uom
            changed = True

        if state.formatted != self._formatted:
            self._formatted = state.formatted
            changed = True

        if state.value != self.status:
            self.status = state.value
            # Let Status setter throw event
            return

        if changed:
            self._last_changed = now()
            self.status_events.notify(self.status_feedback)

    def get_command_value(self, uom: str, cmd: str) -> str | None:
        """Check against the list of UOM States if this is a valid command."""
        if cmd not in UOM_TO_STATES[uom].values():
            _LOGGER.warning("Failed to call %s on %s, invalid command.", cmd, self.address)
            return None
        return list(UOM_TO_STATES[uom].keys())[list(UOM_TO_STATES[uom].values()).index(cmd)]

    def get_groups(self, controller=True, responder=True) -> list[str]:
        """
        Return the groups (scenes) of which this node is a member.

        If controller is True, then the scene it controls is added to the list
        If responder is True, then the scenes it is a responder of are added to
        the list.
        """
        groups: list[str] = []
        for child in self._nodes.all_lower_nodes:
            if child[0] == TAG_GROUP:
                if responder:
                    if self._id in self._nodes[child[2]].members:
                        groups.append(child[2])
                elif controller and self._id in self._nodes[child[2]].controllers:
                    groups.append(child[2])
        return groups

    def get_property_uom(self, prop: str) -> str | None:
        """Get the Unit of Measurement an aux property."""
        if aux_prop := self._aux_properties.get(prop):
            return aux_prop.uom
        return None

    async def secure_lock(self) -> bool:
        """Send a command to securely lock a lock device."""
        if not self.is_lock:
            _LOGGER.warning("Failed to lock %s, it is not a lock node.", self.address)
            return None
        return await self.send_cmd(CMD_SECURE, "1")

    async def secure_unlock(self) -> bool:
        """Send a command to securely lock a lock device."""
        if not self.is_lock:
            _LOGGER.warning("Failed to unlock %s, it is not a lock node.", self.address)
            return None
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
            return None
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

    async def _set_climate_setpoint(self, val: int, setpoint_name: str, setpoint_prop: str) -> bool:
        """Send a command to the device to set the system heat setpoint."""
        if not self.is_thermostat:
            _LOGGER.warning(
                "Failed to set %s setpoint on %s, it is not a thermostat node.",
                setpoint_name,
                self.address,
            )
            return None
        # ISY wants 2 times the temperature for Insteon in order to not lose precision
        if self._uom in ["101", "degrees"]:
            val = 2 * val
        return await self.send_cmd(setpoint_prop, str(val), self.get_property_uom(setpoint_prop))

    async def set_fan_mode(self, cmd: str) -> bool:
        """Send a command to the device to set the fan mode setting."""
        cmd_value = self.get_command_value(UOM_FAN_MODES, cmd)
        if cmd_value:
            return await self.send_cmd(CMD_CLIMATE_FAN_SETTING, cmd_value)
        return False

    async def set_on_level(self, val: int) -> bool:
        """Set the ON Level for a device."""
        if not val or isnan(val) or int(val) not in range(256):
            _LOGGER.warning("Invalid value for On Level for %s. Valid values are 0-255.", self._id)
            return False
        return await self.send_cmd(PROP_ON_LEVEL, str(val))

    async def set_ramp_rate(self, val: int) -> bool:
        """Set the Ramp Rate for a device."""
        if not val or isnan(val) or int(val) not in range(32):
            _LOGGER.warning(
                "Invalid value for Ramp Rate for %s. "
                "Valid values are 0-31. See 'INSTEON_RAMP_RATES' in constants.py for values.",
                self._id,
            )
            return False
        return await self.send_cmd(PROP_RAMP_RATE, str(val))

    async def start_manual_dimming(self) -> bool:
        """Begin manually dimming a device."""
        _LOGGER.warning("'%s' is depreciated, use FADE__ commands instead", CMD_MANUAL_DIM_BEGIN)
        return await self.send_cmd(CMD_MANUAL_DIM_BEGIN)

    async def stop_manual_dimming(self) -> bool:
        """Stop manually dimming  a device."""
        _LOGGER.warning("'%s' is depreciated, use FADE__ commands instead", CMD_MANUAL_DIM_STOP)
        return await self.send_cmd(CMD_MANUAL_DIM_STOP)
