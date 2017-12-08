from ..constants import _change2update_interval
from VarEvents import Property
from time import sleep
from xml.dom import minidom


STATE_PROPERTY = 'ST'
BATLVL_PROPERTY = 'BATLVL'
ATTR_ID = 'id'
ATTR_UOM = 'uom'
ATTR_VALUE = 'value'
ATTR_PREC = 'prec'

FAN_MODE_OFF = 'off'
FAN_MODE_ON = 'on'
FAN_MODE_AUTO = 'auto'

CLIMATE_MODE_OFF = 'off'
CLIMATE_MODE_HEAT = 'heat'
CLIMATE_MODE_COOL = 'cool'
CLIMATE_MODE_AUTO = 'auto'
CLIMATE_MODE_FAN = 'fan'

FAN_MODES = {
    FAN_MODE_OFF: 0,
    FAN_MODE_ON: 7,
    FAN_MODE_AUTO: 8,
}

CLIMATE_MODES = {
    CLIMATE_MODE_OFF: 0,
    CLIMATE_MODE_HEAT: 1,
    CLIMATE_MODE_COOL: 2,
    CLIMATE_MODE_AUTO: 3,
    CLIMATE_MODE_FAN: 4,
}


def parse_xml_properties(xmldoc):
    """
    Args:
        xmldoc: xml document to parse

    Returns:
        (state_val, state_uom, state_prec, aux_props)
    """
    state_val = None
    state_uom = []
    state_prec = ''
    aux_props = []
    state_set = False

    props = xmldoc.getElementsByTagName('property')
    if len(props) > 0:
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
            #print "prop=",prop.toprettyxml();
            units = uom if uom == 'n/a' else uom.split('/')

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
                aux_props.append({
                    ATTR_ID: prop_id,
                    ATTR_VALUE: val,
                    ATTR_PREC: prec,
                    ATTR_UOM: units
                })

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

    :ivar status: A watched property that indicates the current status of the
                  node.
    :ivar hasChildren: Property indicating that there are no more children.
    """

    status = Property(0)
    hasChildren = False

    def __init__(self, parent, nid, nval, name, dimmable=True, spoken=False,
                 notes=False, uom=None, prec=0, aux_properties=None,
                 node_def_id=None, parent_nid=None, type=None):
        self.parent = parent
        self._id = nid
        self.dimmable = dimmable
        self.name = name
        self._notes = notes
        self.uom = uom
        self.prec = prec
        self._spoken = spoken
        self.aux_properties = aux_properties or {}
        self.node_def_id = node_def_id
        self.type = type

        if(parent_nid != nid):
            self.parent_nid = parent_nid
        else:
            self.parent_nid = None

        self.status = nval
        self.status.reporter = self.__report_status__

        self.controlEvents = EventEmitter()

    def __str__(self):
        """ Returns a string representation of the node. """
        return 'Node(' + self._id + ')'

    @property
    def nid(self):
        return self._id

    def __report_status__(self, new_val):
        self.on(new_val)

    def update(self, waitTime=0, hint=None):
        """ Update the value of the node from the controller. """
        if not self.parent.parent.auto_update:
            sleep(waitTime)
            xml = self.parent.parent.conn.updateNode(self._id)

            if xml is not None:
                try:
                    xmldoc = minidom.parseString(xml)
                except:
                    self.parent.parent.log.error('ISY Could not parse nodes,' +
                                                 'poorly formatted XML.')
                else:
                    state_val, state_uom, state_prec, aux_props = parse_xml_properties(
                        xmldoc)

                    self.aux_properties = {}
                    for prop in aux_props:
                        self.aux_properties[prop.get(ATTR_ID)] = prop

                    self.uom = state_uom
                    self.prec = state_prec
                    self.status.update(state_val, silent=True)
                    self.parent.parent.log.info('ISY updated node: ' +
                                                self._id)
            else:
                self.parent.parent.log.warning('ISY could not update node: ' +
                                               self._id)
        elif hint is not None:
            # assume value was set correctly, auto update will correct errors
            self.status.update(hint, silent=True)
            self.parent.parent.log.info('ISY updated node: ' + self._id)

    def off(self):
        """ Turns the node off. """
        response = self.parent.parent.conn.nodeOff(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not turn off node: ' +
                                           self._id)
            return False
        else:
            self.parent.parent.log.info('ISY turned off node: ' + self._id)
            self.update(_change2update_interval, hint=0)
            return True

    def on(self, val=None):
        """
        Turns the node on.

        |  [optional] val: The value brightness value (0-255) to set the node to
        """
        response = self.parent.parent.conn.nodeOn(self._id, val)

        if response is None:
            self.parent.parent.log.warning('ISY could not turn on node: ' +
                                           self._id)
            return False
        else:
            if val is None:
                self.parent.parent.log.info('ISY turned on node: ' + self._id)
                val = 255
            else:
                self.parent.parent.log.info('ISY turned on node: ' + self._id +
                                            ', To value: ' + str(val))
                val = int(val)
            self.update(_change2update_interval, hint=val)
            return True

    def fastoff(self):
        """ Turns the node fast off. """
        response = self.parent.parent.conn.nodeFastOff(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not fast off node: ' +
                                           self._id)
            return False
        else:
            self.parent.parent.log.info('ISY turned did a fast off with node: '
                                        + self._id)
            self.update(_change2update_interval, hint=0)
            return True

    def faston(self):
        """ Turns the node fast on. """
        response = self.parent.parent.conn.nodeFastOn(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not fast on node: ' +
                                           self._id)
            return False
        else:
            self.parent.parent.log.info('ISY did a fast on with node: ' +
                                        self._id)
            self.update(_change2update_interval, hint=255)
            return True

    def bright(self):
        """ Brightens the node by one step. """
        response = self.parent.parent.conn.nodeBright(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not brighten node: ' +
                                           self._id)
            return False
        else:
            self.parent.parent.log.info('ISY brightened node: ' + self._id)
            self.update(_change2update_interval)
            return True

    def dim(self):
        """ Dims the node by one step. """
        response = self.parent.parent.conn.nodeDim(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not dim node: ' +
                                           self._id)
            return False
        else:
            self.parent.parent.log.info('ISY dimmed node: ' + self._id)
            self.update(_change2update_interval)
            return True

    def _fan_mode(self, mode):
        """ Sends a command to the climate device to set the fan mode. """
        if not hasattr(FAN_MODES, mode):
            self.parent.parent.log.warning('Invalid fan mode: ' + mode)
            return False

        response = self.parent.parent.conn.nodeCliFS(FAN_MODES[mode])

        if response is None:
            self.parent.parent.log.warning('ISY could not send command: ' +
                                           self._id)
            return False
        else:
            self.parent.parent.log.info('ISY command sent: ' + self._id)
            self.update(_change2update_interval)
            return True

    def fan_auto(self):
        """ Sends a command to the climate device to set fan mode=auto. """
        return self._fan_mode(FAN_MODE_AUTO)

    def fan_on(self):
        """ Sends a command to the climate device to set fan mode=on. """
        return self._fan_mode(FAN_MODE_ON)

    def fan_off(self):
        """ Sends a command to the climate device to set fan mode=off.  """
        return self._fan_mode(FAN_MODE_OFF)

    def _climate_mode(self, mode):
        """ Sends a command to the climate device to set the system mode. """
        if not hasattr(CLIMATE_MODES, mode):
            self.parent.parent.log.warning('Invalid climate mode: ' + mode)
            return False

        response = self.parent.parent.nodeCliMD(CLIMATE_MODES[mode])

        if response is None:
            self.parent.parent.log.warning('ISY could not send command: ' +
                                           self._id)
            return False
        else:
            self.parent.parent.log.info('ISY command sent: ' + self._id)
            self.update(_change2update_interval)
            return True

    def climate_off(self):
        """ Sends a command to the device to set the system mode=off. """
        return self._climate_mode(CLIMATE_MODE_OFF)

    def climate_auto(self):
        """ Sends a command to the device to set the system mode=auto. """
        return self._climate_mode(CLIMATE_MODE_AUTO)

    def climate_heat(self):
        """ Sends a command to the device to set the system mode=heat. """
        return self._climate_mode(CLIMATE_MODE_HEAT)

    def climate_cool(self):
        """ Sends a command to the device to set the system mode=cool. """
        return self._climate_mode(CLIMATE_MODE_COOL)

    def climate_setpoint(self, val):
        """ Sends a command to the device to set the system setpoints. """
        # For some reason, wants 2 times the temperature
        for cmd in ['nodeCliSPH', 'nodeCliSPC']:
            response = getattr(self.parent.parent, cmd)(2 * val)

            if response is None:
                self.parent.parent.log.warning('ISY could not send command: ' +
                                               self._id)
                return False

        self.parent.parent.log.info('ISY command sent: ' + self._id)
        self.update(_change2update_interval)
        return True

    def climate_setpoint_heat(self, val):
        """ Sends a command to the device to set the system heat setpoint. """
        # For some reason, wants 2 times the temperature
        response = self.parent.parent.nodeCliSPH(2 * val)

        if response is None:
            self.parent.parent.log.warning('ISY could not send command: ' +
                                           self._id)
            return False
        else:
            self.parent.parent.log.info('ISY command sent: ' + self._id)
            self.update(_change2update_interval)
            return True

    def climate_setpoint_cool(self, val):
        """ Sends a command to the device to set the system cool setpoint. """
        # For some reason, wants 2 times the temperature
        response = self.parent.parent.nodeCliSPC(2 * val)

        if response is None:
            self.parent.parent.log.warning('ISY could not send command: ' +
                                           self._id)
            return False
        else:
            self.parent.parent.log.info('ISY command sent: ' + self._id)
            self.update(_change2update_interval)
            return True

    def lock(self):
        """ Sends a command via secure mode to z-wave locks."""
        response = self.parent.parent.conn.nodeSecMd(self._id, '1')

        if response is None:
            self.parent.parent.log.warning('ISY could not send command: ' +
                                           self._id)
            return False
        else:
            self.parent.parent.log.info('ISY command sent: ' + self._id)
            self.update(_change2update_interval)
            return True

    def unlock(self):
        """ Sends a command via secure mode to z-wave locks."""
        response = self.parent.parent.conn.nodeSecMd(self._id, '0')

        if response is None:
            self.parent.parent.log.warning('ISY could not send command: ' +
                                           self._id)
            return False
        else:
            self.parent.parent.log.info('ISY command sent: ' + self._id)
            self.update(_change2update_interval)
            return True

    def _get_notes(self):
        #if not self._notes:
        self._notes = self.parent.parseNotes(self.parent.parent.conn.getNodeNotes(self._id))

    def get_groups(self, controller=True, responder=True):
        """
        Returns the groups (scenes) that this node is a member of.
        If controller is True, then the scene it controls is added to the list
        If responder is True, then the scenes it is a responder of are added to the list
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
        Returns the parent node object of this node. Typically this is for
        devices that are represented as multiple nodes in the ISY, such as
        door and leak sensors. Returns None if there is no parent.
        """
        try:
            return self.parent.getByID(self.parent_nid)
        except:
            return None

    @property
    def spoken(self):
        """Returns the text string of the Spoken property inside the node notes"""
        self._get_notes()
        return self._notes['spoken']
