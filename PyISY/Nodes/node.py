"""Representation of a node from an ISY."""
from time import sleep
from xml.dom import minidom

from VarEvents import Property

from ..constants import (ATTR_FORMATTED, ATTR_GROUP, ATTR_ID, ATTR_PREC,
                         ATTR_UOM, ATTR_VALUE, BATLVL_PROPERTY,
                         CLIMATE_SETPOINT_MIN_GAP, COMMAND_FRIENDLY_NAME,
                         COMMAND_NAME, STATE_PROPERTY, UOM_TO_STATES,
                         UPDATE_INTERVAL, VALUE_UNKNOWN, XML_PARSE_ERROR)
from ..events import EventEmitter
from ..helpers import parse_xml_properties


class Node:
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

    status = Property(0)
    hasChildren = False

    def __init__(self, nodes, nid, name, state, spoken=False, notes=False,
                 aux_properties=None, devtype_cat=None, node_def_id=None,
                 parent_nid=None, dev_type=None, enabled=None):
        """Initialize a Node class."""
        self._nodes = nodes
        self.isy = nodes.isy
        self._id = nid
        self.name = name
        self._notes = notes
        self._spoken = spoken
        self.aux_properties = aux_properties \
            if aux_properties is not None else {}
        self.devtype_cat = devtype_cat
        self.node_def_id = node_def_id
        self.type = dev_type
        self.enabled = enabled if enabled is not None else True
        self.parent_nid = parent_nid if parent_nid != nid else None
        self.uom = state.get(ATTR_UOM, '')
        self.prec = state.get(ATTR_PREC, '0')
        self.formatted = state.get(ATTR_FORMATTED, str(self.status))
        self.status = state.get(ATTR_VALUE, VALUE_UNKNOWN)
        self.status.reporter = self.__report_status__
        self.controlEvents = EventEmitter()

    def __str__(self):
        """Return a string representation of the node."""
        return 'Node({})'.format(self._id)

    @property
    def nid(self):
        """Return the Node ID."""
        return self._id

    @property
    def dimmable(self):
        """
        Return the best guess if this is a dimmable node.

        Check ISYv4 UOM, then Insteon and Z-Wave Types for dimmable types.
        """
        dimmable = '%' in str(self.uom) or \
            (isinstance(self.type, str) and self.type.startswith("1.")) or \
            (self.devtype_cat is not None and
             self.devtype_cat in ['109', '119'])
        return dimmable

    def __report_status__(self, new_val):
        """Report the status of the node."""
        self.on(new_val)

    def update(self, wait_time=0, hint=None):
        """Update the value of the node from the controller."""
        if not self.isy.auto_update:
            sleep(wait_time)
            xml = self.isy.conn.updateNode(self._id)

            if xml is not None:
                try:
                    xmldoc = minidom.parseString(xml)
                except:
                    self.isy.log.error("%s: Nodes", XML_PARSE_ERROR)
                else:
                    state, aux_props = parse_xml_properties(xmldoc)
                    self.aux_properties.update(aux_props)
                    self.uom = state[ATTR_UOM]
                    self.prec = state[ATTR_PREC]
                    self.status.update(state[ATTR_VALUE], silent=True)
                    self.isy.log.debug('ISY updated node: %s', self._id)
            else:
                self.isy.log.warning('ISY could not update node: %s', self._id)
        elif hint is not None:
            # assume value was set correctly, auto update will correct errors
            self.status.update(hint, silent=True)
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
        try:
            return self._nodes.get_by_id(self.parent_nid)
        except:
            return None

    @property
    def spoken(self):
        """Return the string of the Spoken property inside the node notes."""
        self._notes = self._nodes.parse_notes(self._id)
        return self._notes['spoken']

    """
    NODE CONTROL COMMANDS.

    Most are added dynamically, these are special cases.
    """
    def on(self, val=255):
        """
        Turn the node on.

        |  [optional] val: The value brightness value (0-255) for the node.
        """
        if val is None:
            cmd = 'DON'
        elif int(val) > 0:
            cmd = 'DON'
            val = str(val) if int(val) < 255 else None
        else:
            cmd = 'DOF'
            val = None
        return self.send_cmd(cmd, val)

    def send_cmd(self, cmd, val=None):
        """Send a command to the device."""
        value = str(val) if val is not None else None
        if not self.isy.conn.node_send_cmd(self._id, cmd, value):
            self.isy.log.warning('ISY could not send %s command to %s.',
                                 COMMAND_FRIENDLY_NAME.get(cmd), self._id)
            return False
        self.isy.log.info('ISY command %s sent to %s.',
                          COMMAND_FRIENDLY_NAME.get(cmd), self._id)
        # Special hint case for DON command.
        val = val if not (val is None and cmd == 'DON') else 255
        self.update(UPDATE_INTERVAL, hint=val)
        return True

    def climate_setpoint(self, val):
        """Send a command to the device to set the system setpoints."""
        adjustment = int(CLIMATE_SETPOINT_MIN_GAP / 2.0)
        heat_cmd = self.climate_setpoint_heat(val - adjustment)
        cool_cmd = self.climate_setpoint_cool(val + adjustment)
        return heat_cmd and cool_cmd

    def climate_setpoint_heat(self, val):
        """Send a command to the device to set the system heat setpoint."""
        # For some reason, wants 2 times the temperature for Insteon
        if self.uom in ['101', 'degrees']:
            val = 2 * val
        return self.send_cmd('CLISPH', str(val))

    def climate_setpoint_cool(self, val):
        """Send a command to the device to set the system heat setpoint."""
        # For some reason, wants 2 times the temperature for Insteon
        if self.uom in ['101', 'degrees']:
            val = 2 * val
        return self.send_cmd('CLISPC', str(val))
