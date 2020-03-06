"""Representation of a node from an ISY."""
from time import sleep
from xml.dom import minidom

from ..constants import (
    ATTR_UNIT_OF_MEASURE,
    CLIMATE_SETPOINT_MIN_GAP,
    CMD_CLIMATE_FAN_SPEED,
    CMD_CLIMATE_MODE,
    CMD_MANUAL_DIM_BEGIN,
    CMD_MANUAL_DIM_STOP,
    CMD_SECURE,
    METHOD_GET,
    PROP_SETPOINT_COOL,
    PROP_SETPOINT_HEAT,
    PROP_STATUS,
    PROTO_ZWAVE,
    TAG_GROUP,
    THERMOSTAT_TYPES,
    THERMOSTAT_ZWAVE_CAT,
    UOM_CLIMATE_MODES,
    UOM_FAN_SPEEDS,
    UOM_TO_STATES,
    URL_NODES,
    XML_PARSE_ERROR,
)
from ..helpers import parse_xml_properties
from .handlers import EventEmitter
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
    |  devtype_cat: Device Type Category (used for Z-Wave Nodes.)
    |  node_def_id: Node Definition ID (used for ISY firmwares >=v5)
    |  parent_nid: Node ID of the parent node
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
        devtype_cat=None,
        node_def_id=None,
        parent_nid=None,
        device_type=None,
        enabled=None,
        node_server=None,
        protocol=None,
        family_id=None,
    ):
        """Initialize a Node class."""
        self._devtype_cat = devtype_cat
        self._node_def_id = node_def_id
        self._type = device_type
        self._enabled = enabled if enabled is not None else True
        self._parent_nid = parent_nid if parent_nid != address else None
        self._uom = state.uom
        self._prec = state.prec
        self._formatted = state.formatted
        self._node_server = node_server
        self._protocol = protocol
        self.status.update(state.value, force=True, silent=True)
        self.control_events = EventEmitter()
        super().__init__(
            nodes, address, name, family_id=family_id, aux_properties=aux_properties
        )

    @property
    def protocol(self):
        """Return the device standard used (Z-Wave, Zigbee, Insteon, Node Server)."""
        return self._protocol

    @property
    def node_server(self):
        """Return the node server parent slot (used for v5 Node Server devices)."""
        return self._node_server

    @property
    def devtype_cat(self):
        """Return the device type category (used for Z-Wave devices)."""
        return self._devtype_cat

    @property
    def node_def_id(self):
        """Return the node definition id (used for ISYv5)."""
        return self._node_def_id

    @property
    def type(self):
        """Return the device typecode (Used for Insteon)."""
        return self._type

    @property
    def enabled(self):
        """Return if the device is enabled or not in the ISY."""
        return self._enabled

    @property
    def uom(self):
        """Return the unit of measurement for the device."""
        return self._uom

    def update_uom(self, value):
        """Set the unit of measurement if not provided initially."""
        if value and self._uom != value:
            self._uom = value

    @property
    def prec(self):
        """Return the precision of the raw device value."""
        return self._prec

    def update_precision(self, value):
        """Set the unit of measurement if not provided initially."""
        if value and self._prec != value:
            self._prec = value

    @property
    def formatted(self):
        """Return the formatted value with units, if provided."""
        return self._formatted

    @property
    def dimmable(self):
        """
        Return the best guess if this is a dimmable node.

        Check ISYv4 UOM, then Insteon and Z-Wave Types for dimmable types.
        """
        dimmable = (
            "%" in str(self._uom)
            or (isinstance(self._type, str) and self._type.startswith("1."))
            or (self._devtype_cat is not None and self._devtype_cat in ["109", "119"])
        )
        return dimmable

    @property
    def is_thermostat(self):
        """Determine if this device is a thermostat/climate control device."""
        return (
            self.type and any([self.type.startswith(t) for t in THERMOSTAT_TYPES])
        ) or (self.devtype_cat and any(self.devtype_cat in THERMOSTAT_ZWAVE_CAT))

    @property
    def is_lock(self):
        """Determine if this device is a door lock type."""
        return (self.type and self.type.startswith("4.64")) or (
            self.protocol == PROTO_ZWAVE and self.devtype_cat == "111"
        )

    def update(self, wait_time=0, hint=None, xmldoc=None):
        """Update the value of the node from the controller."""
        if not self.isy.auto_update and not xmldoc:
            sleep(wait_time)
            req_url = self.isy.conn.compile_url(
                [URL_NODES, self._id, METHOD_GET, PROP_STATUS]
            )
            xml = self.isy.conn.request(req_url)
            try:
                xmldoc = minidom.parseString(xml)
            except (AttributeError, KeyError, ValueError, TypeError, IndexError):
                self.isy.log.error("%s: Nodes", XML_PARSE_ERROR)
                return
        elif hint is not None:
            # assume value was set correctly, auto update will correct errors
            self.status.update(hint, silent=True)
            self.isy.log.debug("ISY updated node: %s", self._id)
            return

        if xmldoc is None:
            self.isy.log.warning("ISY could not update node: %s", self._id)
            return

        state, aux_props = parse_xml_properties(xmldoc)
        self._aux_properties.update(aux_props)
        self._uom = state.uom if state.uom != "" else self._uom
        self._prec = state.prec if state.prec != "0" else self._prec
        self._formatted = state.formatted
        self.status.update(state.value, silent=True)
        self.isy.log.debug("ISY updated node: %s", self._id)

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

    @property
    def parent_node(self):
        """
        Return the parent node object of this node.

        Typically this is for devices that are represented as multiple nodes in
        the ISY, such as door and leak sensors.
        Return None if there is no parent.

        """
        if self._parent_nid:
            return self._nodes.get_by_id(self._parent_nid)
        return None

    def get_command_value(self, uom, cmd):
        """Check against the list of UOM States if this is a valid command."""
        if not cmd in UOM_TO_STATES[uom].values():
            self.isy.log.warning(
                "Failed to call %s on %s, invalid command.", cmd, self.address
            )
            return None
        return list(UOM_TO_STATES[uom].keys())[
            list(UOM_TO_STATES[uom].values()).index(cmd)
        ]

    def get_property_uom(self, prop):
        """Get the Unit of Measurement for Z-Wave Climate Settings."""
        if self._devtype_cat and self._aux_properties.get(prop):
            return self._aux_properties[prop].uom
        return None

    def start_manual_dimming(self):
        """Begin manually dimming a device."""
        return self.send_cmd(CMD_MANUAL_DIM_BEGIN)

    def stop_manual_dimming(self):
        """Stop manually dimming  a device."""
        return self.send_cmd(CMD_MANUAL_DIM_STOP)

    def set_climate_setpoint(self, val):
        """Send a command to the device to set the system setpoints."""
        if not self.is_thermostat:
            self.isy.log.warning(
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
        if not self.is_thermostat:
            self.isy.log.warning(
                "Failed to set heat setpoint on %s, it is not a thermostat node.",
                self.address,
            )
            return
        # For some reason, wants 2 times the temperature for Insteon
        if self._uom in ["101", "degrees"]:
            val = 2 * val
        return self.send_cmd(
            PROP_SETPOINT_HEAT, str(val), self.get_property_uom(PROP_SETPOINT_HEAT)
        )

    def set_climate_setpoint_cool(self, val):
        """Send a command to the device to set the system heat setpoint."""
        if not self.is_thermostat:
            self.isy.log.warning(
                "Failed to set cool setpoint on %s, it is not a thermostat node.",
                self.address,
            )
            return
        # For some reason, wants 2 times the temperature for Insteon
        if self._uom in ["101", "degrees"]:
            val = 2 * val
        return self.send_cmd(
            PROP_SETPOINT_COOL, str(val), self.get_property_uom(PROP_SETPOINT_COOL)
        )

    def set_fan_speed(self, cmd):
        """Send a command to the device to set the fan speed."""
        cmd_value = self.get_command_value(UOM_FAN_SPEEDS, cmd)
        if cmd_value:
            return self.send_cmd(CMD_CLIMATE_FAN_SPEED, cmd_value)
        return False

    def set_climate_mode(self, cmd):
        """Send a command to the device to set the climate mode."""
        if not self.is_thermostat:
            self.isy.log.warning(
                "Failed to set setpoint on %s, it is not a thermostat node.",
                self.address,
            )
        cmd_value = self.get_command_value(UOM_CLIMATE_MODES, cmd)
        if cmd_value:
            return self.send_cmd(CMD_CLIMATE_MODE, cmd_value)
        return False

    def secure_lock(self):
        """Send a command to securely lock a lock device."""
        if not self.is_lock:
            self.isy.log.warning(
                "Failed to lock %s, it is not a lock node.", self.address
            )
            return
        return self.send_cmd(CMD_SECURE, "1")

    def secure_unlock(self):
        """Send a command to securely lock a lock device."""
        if not self.is_lock:
            self.isy.log.warning(
                "Failed to unlock %s, it is not a lock node.", self.address
            )
            return
        return self.send_cmd(CMD_SECURE, "0")
