"""Representation of a node from an ISY."""
from time import sleep
from xml.dom import minidom

from VarEvents import Property

from ..constants import UPDATE_INTERVAL

STATE_PROPERTY = 'ST'
BATLVL_PROPERTY = 'BATLVL'
ATTR_ID = 'id'
ATTR_UOM = 'uom'
ATTR_VALUE = 'value'
ATTR_PREC = 'prec'

FAN_MODE_ON = 'on'
FAN_MODE_AUTO = 'auto'

CLIMATE_MODE_OFF = 'off'
CLIMATE_MODE_HEAT = 'heat'
CLIMATE_MODE_COOL = 'cool'
CLIMATE_MODE_AUTO = 'auto'
CLIMATE_MODE_FAN_ONLY = 'fan_only'
CLIMATE_MODE_PROG_AUTO = 'program_auto'
CLIMATE_MODE_PROG_HEAT = 'program_heat'
CLIMATE_MODE_PROG_COOL = 'program_cool'

CLIMATE_SETPOINT_MIN_GAP = 2

FAN_MODES = {
    FAN_MODE_ON: 7,
    FAN_MODE_AUTO: 8,
}

CLIMATE_MODES = {
    CLIMATE_MODE_OFF: 0,
    CLIMATE_MODE_HEAT: 1,
    CLIMATE_MODE_COOL: 2,
    CLIMATE_MODE_AUTO: 3,
    CLIMATE_MODE_FAN_ONLY: 4,
    CLIMATE_MODE_PROG_AUTO: 5,
    CLIMATE_MODE_PROG_HEAT: 6,
    CLIMATE_MODE_PROG_COOL: 7,
}


def parse_xml_properties(xmldoc):
    """
    Parse the xml properties string.

    Args:
        xmldoc: xml document to parse

    Returns:
        (state_val, state_uom, state_prec, aux_props)

    """
    state_val = None
    state_uom = ''
    state_prec = ''
    aux_props = {}
    state_set = False

    props = xmldoc.getElementsByTagName('property')
    if not props:
        return state_val, state_uom, state_prec, aux_props

    for prop in props:
        attrs = prop.attributes
        if ATTR_ID in prop.attributes.keys():
            prop_id = attrs[ATTR_ID].value
        if ATTR_UOM in prop.attributes.keys():
            uom = attrs[ATTR_UOM].value
        else:
            uom = ''
        if ATTR_VALUE in prop.attributes.keys():
            val = attrs[ATTR_VALUE].value
        if ATTR_PREC in prop.attributes.keys():
            prec = attrs[ATTR_PREC].value
        else:
            prec = '0'

        # ISY firmwares < 5 return a list of possible units.
        # ISYv5+ returns a UOM string which is checked against the SDK.
        # Only return a list if the UOM should be a list.
        units = uom.split('/') if ('/' in uom and uom != 'n/a') else uom

        val = val.strip()
        if val == "":
            val = -1 * float('inf')
        else:
            val = int(val)

        if prop_id == STATE_PROPERTY:
            state_val = val
            state_uom = units
            state_prec = prec
            state_set = True
        elif prop_id == BATLVL_PROPERTY and not state_set:
            state_val = val
            state_uom = units
            state_prec = prec
        else:
            aux_props[prop_id] = {
                ATTR_ID: prop_id,
                ATTR_VALUE: val,
                ATTR_PREC: prec,
                ATTR_UOM: units
            }

    return state_val, state_uom, state_prec, aux_props


class EventEmitter(object):
    def __init__(self):
        self._subscribers = []

    def subscribe(self, callback):
        listener = EventListener(self, callback)
        self._subscribers.append(listener)
        return listener

    def unsubscribe(self, listener):
        self._subscribers.remove(listener)

    def notify(self, event):
        for subscriber in self._subscribers:
            subscriber.callback(event)


class EventListener(object):
    def __init__(self, emitter, callback):
        self._emitter = emitter
        self.callback = callback

    def unsubscribe(self):
        self._emitter.unsubscribe(self)


class EventResult(dict):
    """Class to hold result of a command event."""

    def __init__(self, event, nval=None, prec=None, uom=None):
        """Initialize an event result."""
        super().__init__(self, event=event, nval=nval, prec=prec, uom=uom)
        self._event = event
        self._nval = nval
        self._prec = prec
        self._uom = uom

    @property
    def event(self):
        """Report the event control string."""
        return self._event

    @property
    def nval(self):
        """Report the value, if there was one."""
        return self._nval

    @property
    def prec(self):
        """Report the precision, if there was one."""
        return self._prec

    @property
    def uom(self):
        """Report the unit of measure, if there was one."""
        return self._uom

    def __str__(self):
        """Return just the event title to prevent breaking changes."""
        return str(self.event)

    __repr__ = __str__


class Node(object):
    """
    This class handles ISY nodes.

    |  parent: The node manager object.
    |  nid: The Node ID.
    |  nval: The current Node value.
    |  name: The node name.
    |  [optional] dimmable: Default True. Boolean of whether the node is
       dimmable.
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

    def __init__(self, parent, nid, nval, name, dimmable=True, spoken=False,
                 notes=False, uom=None, prec=0, aux_properties={},
                 devtype_cat=None, node_def_id=None, parent_nid=None,
                 dev_type=None):
        """Initialize a Node class."""
        self.parent = parent
        self._conn = parent.parent.conn
        self._log = parent.parent.log
        self._id = nid
        self.dimmable = dimmable
        self.name = name
        self._notes = notes
        self.uom = uom
        self.prec = prec
        self._spoken = spoken
        self.aux_properties = aux_properties
        self.devtype_cat = devtype_cat
        self.node_def_id = node_def_id
        self.type = dev_type
        self.parent_nid = parent_nid if parent_nid != nid else None
        self.status = nval
        self.status.reporter = self.__report_status__
        self.controlEvents = EventEmitter()

    def __str__(self):
        """Return a string representation of the node."""
        return 'Node({})'.format(self._id)

    @property
    def nid(self):
        """Return the Node ID."""
        return self._id

    def __report_status__(self, new_val):
        """Report the status of the node."""
        self.on(new_val)

    def update(self, wait_time=0, hint=None):
        """Update the value of the node from the controller."""
        if not self.parent.parent.auto_update:
            sleep(wait_time)
            xml = self._conn.updateNode(self._id)

            if xml is not None:
                try:
                    xmldoc = minidom.parseString(xml)
                except:
                    self._log.error('ISY Could not parse nodes,' +
                                    'poorly formatted XML.')
                else:
                    state_val, state_uom, state_prec, aux_props = \
                        parse_xml_properties(xmldoc)

                    self.aux_properties.update(aux_props)
                    self.uom = state_uom
                    self.prec = state_prec
                    self.status.update(state_val, silent=True)
                    self._log.debug('ISY updated node: %s', self._id)
            else:
                self._log.warning('ISY could not update node: %s', self._id)
        elif hint is not None:
            # assume value was set correctly, auto update will correct errors
            self.status.update(hint, silent=True)
            self._log.debug('ISY updated node: %s', self._id)

    def off(self):
        """Turn the node off."""
        if not self._conn.node_send_cmd(self._id, 'DOF'):
            self._log.warning('ISY could not turn off node: %s', self._id)
            return False
        self._log.info('ISY turned off node: %s', self._id)
        self.update(UPDATE_INTERVAL, hint=0)
        return True

    def on(self, val=None):
        """
        Turn the node on.

        |  [optional] val: The value brightness value (0-255) for the node.
        """
        if val is None:
            response = self._conn.node_send_cmd(self._id, 'DON')
        elif val > 0:
            response = self._conn.node_send_cmd(self._id, 'DOF',
                                                str(min(255, val)))
        else:
            response = self._conn.node_send_cmd(self._id, 'DOF')

        if response is None:
            self._log.warning('ISY could not turn on node: %s', self._id)
            return False

        if val is None:
            self._log.info('ISY turned on node: %s', self._id)
            val = 255
        else:
            self._log.info('ISY turned on node: %s, To value: %s',
                           self._id, str(val))
            val = int(val)
        self.update(UPDATE_INTERVAL, hint=val)
        return True

    def fastoff(self):
        """Turn the node fast off."""
        if not self._conn.node_send_cmd(self._id, 'DFOF'):
            self._log.warning('ISY could not fast off node: %s', self._id)
            return False
        self._log.info('ISY turned did a fast off with node: %s', self._id)
        self.update(UPDATE_INTERVAL, hint=0)
        return True

    def faston(self):
        """Turn the node fast on."""
        if not self._conn.node_send_cmd(self._id, 'DFON'):
            self._log.warning('ISY could not fast on node: %s', self._id)
            return False
        self._log.info('ISY did a fast on with node: %s', self._id)
        self.update(UPDATE_INTERVAL, hint=255)
        return True

    def bright(self):
        """Brighten the node by one step."""
        if not self._conn.node_send_cmd(self._id, 'BRT'):
            self._log.warning('ISY could not brighten node: %s', self._id)
            return False
        self._log.info('ISY brightened node: %s', self._id)
        self.update(UPDATE_INTERVAL)
        return True

    def dim(self):
        """Dim the node by one step."""
        if not self._conn.node_send_cmd(self._id, 'DIM'):
            self._log.warning('ISY could not dim node: %s', self._id)
            return False
        self._log.info('ISY dimmed node: %s', self._id)
        self.update(UPDATE_INTERVAL)
        return True

    def send_cmd(self, cmd, val):
        """Send a command to the device to set the system heat setpoint."""
        if not self._conn.node_send_cmd(self._id, cmd, str(val)):
            self._log.warning('ISY could not send command: %s', self._id)
            return False
        self._log.info('ISY command sent: %s', self._id)
        self.update(UPDATE_INTERVAL)
        return True

    def _fan_mode(self, mode):
        """Send a command to the climate device to set the fan mode."""
        if mode not in FAN_MODES:
            self._log.warning('ISY received invalid fan mode: ' + mode)
            return False
        return self.send_cmd('CLIFS', FAN_MODES[mode])

    def fan_by_mode(self, mode):
        """Send a command to the climate device to set fan mode=auto."""
        return self._fan_mode(mode)

    def fan_auto(self):
        """Send a command to the climate device to set fan mode=auto."""
        return self._fan_mode(FAN_MODE_AUTO)

    def fan_on(self):
        """Send a command to the climate device to set fan mode=on."""
        return self._fan_mode(FAN_MODE_ON)

    def _climate_mode(self, mode):
        """Send a command to the climate device to set the system mode."""
        if mode not in CLIMATE_MODES:
            self._log.warning('ISY received invalid climate mode: ' + mode)
            return False
        return self.send_cmd('CLIMD', CLIMATE_MODES[mode])

    def climate_by_mode(self, mode):
        """Send a command to the device to set the system to a given mode."""
        return self._climate_mode(mode)

    def climate_off(self):
        """Send a command to the device to set the system mode=off."""
        return self._climate_mode(CLIMATE_MODE_OFF)

    def climate_auto(self):
        """Send a command to the device to set the system mode=auto."""
        return self._climate_mode(CLIMATE_MODE_AUTO)

    def climate_heat(self):
        """Send a command to the device to set the system mode=heat."""
        return self._climate_mode(CLIMATE_MODE_HEAT)

    def climate_cool(self):
        """Send a command to the device to set the system mode=cool."""
        return self._climate_mode(CLIMATE_MODE_COOL)

    def climate_prog_auto(self):
        """Send a command to the device to set the system mode=auto."""
        return self._climate_mode(CLIMATE_MODE_PROG_AUTO)

    def climate_prog_heat(self):
        """Send a command to the device to set the system mode=heat."""
        return self._climate_mode(CLIMATE_MODE_PROG_HEAT)

    def climate_prog_cool(self):
        """Send a command to the device to set the system mode=cool."""
        return self._climate_mode(CLIMATE_MODE_PROG_COOL)

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

    def lock(self):
        """Send a command via secure mode to z-wave locks."""
        return self.send_cmd('SECMD', '1')

    def unlock(self):
        """Send a command via secure mode to z-wave locks."""
        return self.send_cmd('SECMD', '0')

    def _get_notes(self):
        self._notes = self.parent.parseNotes(self._conn.getNodeNotes(self._id))

    def get_groups(self, controller=True, responder=True):
        """
        Return the groups (scenes) of which this node is a member.

        If controller is True, then the scene it controls is added to the list
        If responder is True, then the scenes it is a responder of are added to
        the list.
        """
        groups = []
        for child in self.parent.parent.nodes.allLowerNodes:
            if child[0] is 'group':
                if responder:
                    if self._id in self.parent.parent.nodes[child[2]].members:
                        groups.append(child[2])
                elif controller:
                    if self._id in self.parent.parent.nodes[child[2]].controllers:
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
            return self.parent.getByID(self.parent_nid)
        except:
            return None

    @property
    def spoken(self):
        """Return the string of the Spoken property inside the node notes."""
        self._get_notes()
        return self._notes['spoken']
