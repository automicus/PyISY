"""Representation of a node from an ISY."""
from time import sleep
from xml.dom import minidom

from ..constants import (ATTR_FORMATTED, ATTR_GET, ATTR_GROUP, ATTR_PREC,
                         ATTR_UOM, ATTR_VALUE, CLIMATE_SETPOINT_MIN_GAP,
                         STATE_PROPERTY, VALUE_UNKNOWN, XML_PARSE_ERROR)
from ..events import EventEmitter
from ..helpers import parse_xml_properties
from .nodebase import NodeBase


class Node(NodeBase):
    """
    This class handles ISY nodes.

    |  parent: The node manager object.
    |  nid: The Node ID.
    |  nval: The current Node value.
    |  name: The node name.
    |  spoken: The string of the Notes Spoken field.
    |  notes: Notes from the ISY
    |  uom: Unit of Measure returned by the ISY
    |  prec: Precision of the Node (10^-prec)
    |  aux_properties: Additional Properties for the node
    |  devtype_cat: Device Type Category (used for Z-Wave Nodes.)
    |  node_def_id: Node Definition ID (used for ISY firmwares >=v5)
    |  parent_nid: Node ID of the parent node
    |  dev_type: device type.

    :ivar status: A watched property that indicates the current status of the
                  node.
    :ivar hasChildren: Property indicating that there are no more children.
    """

    def __init__(self, nodes, nid, name, state,
                 aux_properties=None, devtype_cat=None, node_def_id=None,
                 parent_nid=None, dev_type=None, enabled=None):
        """Initialize a Node class."""
        self._aux_properties = aux_properties \
            if aux_properties is not None else {}
        self._devtype_cat = devtype_cat
        self._node_def_id = node_def_id
        self._type = dev_type
        self._enabled = enabled if enabled is not None else True
        self._parent_nid = parent_nid if parent_nid != nid else None
        self._uom = state.get(ATTR_UOM, '')
        self._prec = state.get(ATTR_PREC, '0')
        self._formatted = state.get(ATTR_FORMATTED, str(self.status))
        self.status.update(state.get(ATTR_VALUE, VALUE_UNKNOWN),
                           force=True, silent=True)
        self.controlEvents = EventEmitter()
        super().__init__(nodes, nid, name)

    @property
    def aux_properties(self):
        """Return the aux properties that were in the Node Definition."""
        return self._aux_properties

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

    @property
    def prec(self):
        """Return the precision of the raw device value."""
        return self._prec

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
        dimmable = '%' in str(self._uom) or \
            (isinstance(self._type, str) and self._type.startswith("1.")) or \
            (self._devtype_cat is not None and
             self._devtype_cat in ['109', '119'])
        return dimmable

    def update(self, wait_time=0, hint=None, xmldoc=None):
        """Update the value of the node from the controller."""
        if not self.isy.auto_update and not xmldoc:
            sleep(wait_time)
            req_url = self.isy.conn.compile_url(['nodes', self._id,
                                                 ATTR_GET, STATE_PROPERTY])
            xml = self.isy.conn.request(req_url)
            try:
                xmldoc = minidom.parseString(xml)
            except:
                self.isy.log.error("%s: Nodes", XML_PARSE_ERROR)
                return
        elif hint is not None:
            # assume value was set correctly, auto update will correct errors
            self.status.update(hint, silent=True)
            self.isy.log.debug('ISY updated node: %s', self._id)
            return

        if xmldoc is None:
            self.isy.log.warning('ISY could not update node: %s', self._id)
            return

        state, aux_props = parse_xml_properties(xmldoc)
        self._aux_properties.update(aux_props)
        self._uom = state.get(ATTR_UOM, self._uom)
        self._prec = state.get(ATTR_PREC, self._prec)
        value = state.get(ATTR_VALUE, VALUE_UNKNOWN)
        self._formatted = state.get(ATTR_FORMATTED, value)
        self.status.update(value, silent=True)
        self.isy.log.debug('ISY updated node: %s', self._id)

    def get_groups(self, controller=True, responder=True):
        """
        Return the groups (scenes) of which this node is a member.

        If controller is True, then the scene it controls is added to the list
        If responder is True, then the scenes it is a responder of are added to
        the list.
        """
        groups = []
        for child in self._nodes.all_lower_nodes:
            if child[0] == ATTR_GROUP:
                if responder:
                    if self._id in self._nodes[child[2]].members:
                        groups.append(child[2])
                elif controller:
                    if self._id in self._nodes[child[2]] \
                            .controllers:
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

    """
    NODE CONTROL COMMANDS.

    Most are added dynamically, these are special cases.
    """
    def climate_setpoint(self, val):
        """Send a command to the device to set the system setpoints."""
        adjustment = int(CLIMATE_SETPOINT_MIN_GAP / 2.0)
        heat_cmd = self.climate_setpoint_heat(val - adjustment)
        cool_cmd = self.climate_setpoint_cool(val + adjustment)
        return heat_cmd and cool_cmd

    def climate_setpoint_heat(self, val):
        """Send a command to the device to set the system heat setpoint."""
        # For some reason, wants 2 times the temperature for Insteon
        if self._uom in ['101', 'degrees']:
            val = 2 * val
        return self.send_cmd('CLISPH', str(val))

    def climate_setpoint_cool(self, val):
        """Send a command to the device to set the system heat setpoint."""
        # For some reason, wants 2 times the temperature for Insteon
        if self._uom in ['101', 'degrees']:
            val = 2 * val
        return self.send_cmd('CLISPC', str(val))
