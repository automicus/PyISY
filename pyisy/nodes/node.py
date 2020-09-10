"""Representation of a node from an ISY."""
from math import isnan
from time import sleep
from xml.dom import minidom

from ..constants import (
    _LOGGER,
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
    METHOD_GET,
    PROP_ON_LEVEL,
    PROP_RAMP_RATE,
    PROP_SETPOINT_COOL,
    PROP_SETPOINT_HEAT,
    PROP_STATUS,
    PROTO_INSTEON,
    PROTO_ZWAVE,
    TAG_GROUP,
    UOM_CLIMATE_MODES,
    UOM_FAN_MODES,
    UOM_TO_STATES,
    URL_NODES,
    XML_ERRORS,
    XML_PARSE_ERROR,
    ZWAVE_CAT_DIMMABLE,
    ZWAVE_CAT_LOCK,
    ZWAVE_CAT_THERMOSTAT,
)
from ..helpers import EventEmitter, NodeProperty, now, parse_xml_properties
from .nodebase import NodeBase


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
        nodes,
        address,
        name,
        state,
        aux_properties=None,
        zwave_props=None,
        node_def_id=None,
        pnode=None,
        device_type=None,
        enabled=None,
        node_server=None,
        protocol=None,
        family_id=None,
    ):
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
        super().__init__(
            nodes,
            address,
            name,
            state.value,
            family_id=family_id,
            aux_properties=aux_properties,
            pnode=pnode,
        )

    @property
    def dimmable(self):
        """
        Return the best guess if this is a dimmable node.

        DEPRECIATED: USE is_dimmable INSTEAD. Will be removed in future release.
        """
        _LOGGER.info("Node.dimmable is depreciated. Use Node.is_dimmable instead.")
        return self.is_dimmable

    @property
    def enabled(self):
        """Return if the device is enabled or not in the ISY."""
        return self._enabled

    @property
    def formatted(self):
        """Return the formatted value with units, if provided."""
        return self._formatted

    @property
    def is_dimmable(self):
        """
        Return the best guess if this is a dimmable node.

        Check ISYv4 UOM, then Insteon and Z-Wave Types for dimmable types.
        """
        dimmable = (
            "%" in str(self._uom)
            or (
                self._protocol == PROTO_INSTEON
                and self.type
                and any([self.type.startswith(t) for t in INSTEON_TYPE_DIMMABLE])
                and self._id.endswith(INSTEON_SUBNODE_DIMMABLE)
            )
            or (
                self._protocol == PROTO_ZWAVE
                and self._zwave_props is not None
                and self._zwave_props.category in ZWAVE_CAT_DIMMABLE
            )
        )
        return dimmable

    @property
    def is_lock(self):
        """Determine if this device is a door lock type."""
        return (
            self.type and any([self.type.startswith(t) for t in INSTEON_TYPE_LOCK])
        ) or (
            self.protocol == PROTO_ZWAVE
            and self.zwave_props.category
            and self.zwave_props.category in ZWAVE_CAT_LOCK
        )

    @property
    def is_thermostat(self):
        """Determine if this device is a thermostat/climate control device."""
        return (
            self.type
            and any([self.type.startswith(t) for t in INSTEON_TYPE_THERMOSTAT])
        ) or (
            self._protocol == PROTO_ZWAVE
            and self.zwave_props.category
            and self.zwave_props.category in ZWAVE_CAT_THERMOSTAT
        )

    @property
    def node_def_id(self):
        """Return the node definition id (used for ISYv5)."""
        return self._node_def_id

    @property
    def node_server(self):
        """Return the node server parent slot (used for v5 Node Server devices)."""
        return self._node_server

    @property
    def parent_node(self):
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
    def prec(self):
        """Return the precision of the raw device value."""
        return self._prec

    @property
    def protocol(self):
        """Return the device standard used (Z-Wave, Zigbee, Insteon, Node Server)."""
        return self._protocol

    @property
    def type(self):
        """Return the device typecode (Used for Insteon)."""
        return self._type

    @property
    def uom(self):
        """Return the unit of measurement for the device."""
        return self._uom

    @property
    def zwave_props(self):
        """Return the Z-Wave Properties (used for Z-Wave devices)."""
        return self._zwave_props

    def update(self, event=None, wait_time=0, hint=None, xmldoc=None):
        """Update the value of the node from the controller."""
        if not self.isy.auto_update and not xmldoc:
            sleep(wait_time)
            req_url = self.isy.conn.compile_url(
                [URL_NODES, self._id, METHOD_GET, PROP_STATUS]
            )
            xml = self.isy.conn.request(req_url)
            try:
                xmldoc = minidom.parseString(xml)
            except XML_ERRORS:
                _LOGGER.error("%s: Nodes", XML_PARSE_ERROR)
                return
        elif hint is not None:
            # assume value was set correctly, auto update will correct errors
            self.status = hint
            _LOGGER.debug("ISY updated node: %s", self._id)
            return

        if xmldoc is None:
            _LOGGER.warning("ISY could not update node: %s", self._id)
            return

        self._last_update = now()
        state, aux_props = parse_xml_properties(xmldoc)
        self._aux_properties.update(aux_props)
        self.update_state(state)
        _LOGGER.debug("ISY updated node: %s", self._id)

    def update_state(self, state):
        """Update the various state properties when received."""
        if not isinstance(state, NodeProperty):
            _LOGGER.error("Could not update state values. Invalid type provided.")
            return
        changed = False
        self._last_update = now()

        if state.prec != self._prec:
            self._prec = state.prec
            changed = True

        if state.uom != self._uom and state.uom != "":
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

    def get_command_value(self, uom, cmd):
        """Check against the list of UOM States if this is a valid command."""
        if cmd not in UOM_TO_STATES[uom].values():
            _LOGGER.warning(
                "Failed to call %s on %s, invalid command.", cmd, self.address
            )
            return None
        return list(UOM_TO_STATES[uom].keys())[
            list(UOM_TO_STATES[uom].values()).index(cmd)
        ]

    def get_groups(self, controller=True, responder=True):
        """
        Return the groups (scenes) of which this node is a member.

        If controller is True, then the scene it controls is added to the list
        If responder is True, then the scenes it is a responder of are added to
        the list.
        """
        groups = []
        for child in self._nodes.all_lower_nodes:
            if child[0] == TAG_GROUP:
                if responder:
                    if self._id in self._nodes[child[2]].members:
                        groups.append(child[2])
                elif controller:
                    if self._id in self._nodes[child[2]].controllers:
                        groups.append(child[2])
        return groups

    def get_property_uom(self, prop):
        """Get the Unit of Measurement for Z-Wave Climate Settings."""
        if self._protocol == PROTO_ZWAVE and self._aux_properties.get(prop):
            return self._aux_properties[prop].uom
        return None

    def secure_lock(self):
        """Send a command to securely lock a lock device."""
        if not self.is_lock:
            _LOGGER.warning("Failed to lock %s, it is not a lock node.", self.address)
            return
        return self.send_cmd(CMD_SECURE, "1")

    def secure_unlock(self):
        """Send a command to securely lock a lock device."""
        if not self.is_lock:
            _LOGGER.warning("Failed to unlock %s, it is not a lock node.", self.address)
            return
        return self.send_cmd(CMD_SECURE, "0")

    def set_climate_mode(self, cmd):
        """Send a command to the device to set the climate mode."""
        if not self.is_thermostat:
            _LOGGER.warning(
                "Failed to set setpoint on %s, it is not a thermostat node.",
                self.address,
            )
        cmd_value = self.get_command_value(UOM_CLIMATE_MODES, cmd)
        if cmd_value:
            return self.send_cmd(CMD_CLIMATE_MODE, cmd_value)
        return False

    def set_climate_setpoint(self, val):
        """Send a command to the device to set the system setpoints."""
        if not self.is_thermostat:
            _LOGGER.warning(
                "Failed to set setpoint on %s, it is not a thermostat node.",
                self.address,
            )
            return
        adjustment = int(CLIMATE_SETPOINT_MIN_GAP / 2.0)
        heat_cmd = self.set_climate_setpoint_heat(val - adjustment)
        cool_cmd = self.set_climate_setpoint_cool(val + adjustment)
        return heat_cmd and cool_cmd

    def set_climate_setpoint_heat(self, val):
        """Send a command to the device to set the system heat setpoint."""
        return self._set_climate_setpoint(val, "heat", PROP_SETPOINT_HEAT)

    def set_climate_setpoint_cool(self, val):
        """Send a command to the device to set the system heat setpoint."""
        return self._set_climate_setpoint(val, "cool", PROP_SETPOINT_COOL)

    def _set_climate_setpoint(self, val, setpoint_name, setpoint_prop):
        """Send a command to the device to set the system heat setpoint."""
        if not self.is_thermostat:
            _LOGGER.warning(
                "Failed to set %s setpoint on %s, it is not a thermostat node.",
                setpoint_name,
                self.address,
            )
            return
        # ISY wants 2 times the temperature for Insteon in order to not lose precision
        if self._uom in ["101", "degrees"]:
            val = 2 * val
        return self.send_cmd(
            setpoint_prop, str(val), self.get_property_uom(setpoint_prop)
        )

    def set_fan_mode(self, cmd):
        """Send a command to the device to set the fan mode setting."""
        cmd_value = self.get_command_value(UOM_FAN_MODES, cmd)
        if cmd_value:
            return self.send_cmd(CMD_CLIMATE_FAN_SETTING, cmd_value)
        return False

    def set_on_level(self, val):
        """Set the ON Level for a device."""
        if not val or isnan(val) or int(val) not in range(256):
            _LOGGER.warning(
                "Invalid value for On Level for %s. Valid values are 0-255.", self._id
            )
            return False
        return self.send_cmd(PROP_ON_LEVEL, str(val))

    def set_ramp_rate(self, val):
        """Set the Ramp Rate for a device."""
        if not val or isnan(val) or int(val) not in range(32):
            _LOGGER.warning(
                "Invalid value for Ramp Rate for %s. "
                "Valid values are 0-31. See 'INSTEON_RAMP_RATES' in constants.py for values.",
                self._id,
            )
            return False
        return self.send_cmd(PROP_RAMP_RATE, str(val))

    def start_manual_dimming(self):
        """Begin manually dimming a device."""
        _LOGGER.warning(
            f"'{CMD_MANUAL_DIM_BEGIN}' is depreciated. Use Fade Commands instead."
        )
        return self.send_cmd(CMD_MANUAL_DIM_BEGIN)

    def stop_manual_dimming(self):
        """Stop manually dimming  a device."""
        _LOGGER.warning(
            f"'{CMD_MANUAL_DIM_STOP}' is depreciated. Use Fade Commands instead."
        )
        return self.send_cmd(CMD_MANUAL_DIM_STOP)
