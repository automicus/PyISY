"""Base object for nodes and groups."""
from xml.dom import minidom

from ..constants import (
    _LOGGER,
    ATTR_LAST_CHANGED,
    ATTR_LAST_UPDATE,
    ATTR_STATUS,
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
    NODE_FAMILY_ID,
    PROP_ON_LEVEL,
    TAG_ADDRESS,
    TAG_DESCRIPTION,
    TAG_IS_LOAD,
    TAG_LOCATION,
    TAG_SPOKEN,
    UPDATE_INTERVAL,
    URL_NODES,
    URL_NOTES,
    XML_ERRORS,
    XML_PARSE_ERROR,
    XML_TRUE,
)
from ..helpers import EventEmitter, NodeProperty, now, value_from_xml


class NodeBase:
    """Base Object for Nodes and Groups/Scenes."""

    has_children = False

    def __init__(
        self,
        nodes,
        address,
        name,
        status,
        family_id=None,
        aux_properties=None,
        pnode=None,
    ):
        """Initialize a Node Base class."""
        self._aux_properties = aux_properties if aux_properties is not None else {}
        self._family = NODE_FAMILY_ID.get(family_id)
        self._id = address
        self._name = name
        self._nodes = nodes
        self._notes = None
        self._primary_node = pnode
        self._status = status
        self._last_update = now()
        self._last_changed = now()
        self.isy = nodes.isy
        self.status_events = EventEmitter()

    def __str__(self):
        """Return a string representation of the node."""
        return f"{type(self).__name__}({self._id})"

    @property
    def aux_properties(self):
        """Return the aux properties that were in the Node Definition."""
        return self._aux_properties

    @property
    def address(self):
        """Return the Node ID."""
        return self._id

    @property
    def description(self):
        """Return the description of the node from it's notes."""
        if self._notes is None:
            self._notes = self.parse_notes()
        return self._notes[TAG_DESCRIPTION]

    @property
    def family(self):
        """Return the ISY Family category."""
        return self._family

    @property
    def folder(self):
        """Return the folder of the current node as a property."""
        return self._nodes.get_folder(self.address)

    @property
    def is_load(self):
        """Return the isLoad property of the node from it's notes."""
        if self._notes is None:
            self._notes = self.parse_notes()
        return self._notes[TAG_IS_LOAD]

    @property
    def last_changed(self):
        """Return the UTC Time of the last status change for this node."""
        return self._last_changed

    @property
    def last_update(self):
        """Return the UTC Time of the last update for this node."""
        return self._last_update

    @property
    def location(self):
        """Return the location of the node from it's notes."""
        if self._notes is None:
            self._notes = self.parse_notes()
        return self._notes[TAG_LOCATION]

    @property
    def name(self):
        """Return the name of the Node."""
        return self._name

    @property
    def primary_node(self):
        """Return just the parent/primary node address.

        This is similar to Node.parent_node but does not return the whole Node
        class, and will return itself if it is the primary node/group.

        """
        return self._primary_node

    @property
    def spoken(self):
        """Return the text of the Spoken property inside the group notes."""
        if self._notes is None:
            self._notes = self.parse_notes()
        return self._notes[TAG_SPOKEN]

    @property
    def status(self):
        """Return the current node state."""
        return self._status

    @status.setter
    def status(self, value):
        """Set the current node state and notify listeners."""
        if self._status != value:
            self._status = value
            self._last_changed = now()
            self.status_events.notify(self.status_feedback)
        return self._status

    @property
    def status_feedback(self):
        """Return information for a status change event."""
        return {
            TAG_ADDRESS: self.address,
            ATTR_STATUS: self._status,
            ATTR_LAST_CHANGED: self._last_changed,
            ATTR_LAST_UPDATE: self._last_update,
        }

    def parse_notes(self):
        """Parse the notes for a given node.

        Notes are not retrieved unless explicitly request by a property call
        or a call to this function.
        """
        notes_xml = self.isy.conn.request(
            self.isy.conn.compile_url([URL_NODES, self._id, URL_NOTES]), ok404=True
        )
        spoken = None
        is_load = None
        description = None
        location = None
        if notes_xml is not None and notes_xml != "":
            try:
                notesdom = minidom.parseString(notes_xml)
            except XML_ERRORS:
                _LOGGER.error("%s: Node Notes %s", XML_PARSE_ERROR, notes_xml)
            else:
                spoken = value_from_xml(notesdom, TAG_SPOKEN)
                location = value_from_xml(notesdom, TAG_LOCATION)
                description = value_from_xml(notesdom, TAG_DESCRIPTION)
                is_load = value_from_xml(notesdom, TAG_IS_LOAD)
        return {
            TAG_SPOKEN: spoken,
            TAG_IS_LOAD: is_load == XML_TRUE,
            TAG_DESCRIPTION: description,
            TAG_LOCATION: location,
        }

    def update(self, event=None, wait_time=0, hint=None, xmldoc=None):
        """Update the group with values from the controller."""
        self.update_last_update()

    def update_property(self, prop):
        """Update an aux property for the node when received."""
        if not isinstance(prop, NodeProperty):
            _LOGGER.error("Could not update property value. Invalid type provided.")
            return
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
        self.status_events.notify(self.status_feedback)

    def update_last_changed(self, timestamp=None):
        """Set the UTC Time of the last status change for this node."""
        if timestamp is None:
            timestamp = now()
        self._last_changed = timestamp

    def update_last_update(self, timestamp=None):
        """Set the UTC Time of the last update for this node."""
        if timestamp is None:
            timestamp = now()
        self._last_update = timestamp

    def send_cmd(self, cmd, val=None, uom=None, query=None):
        """Send a command to the device."""
        value = str(val) if val is not None else None
        _uom = str(uom) if uom is not None else None
        req = [URL_NODES, str(self._id), METHOD_COMMAND, cmd]
        if value:
            req.append(value)
        if _uom:
            req.append(_uom)
        req_url = self.isy.conn.compile_url(req, query)
        if not self.isy.conn.request(req_url):
            _LOGGER.warning(
                "ISY could not send %s command to %s.",
                COMMAND_FRIENDLY_NAME.get(cmd),
                self._id,
            )
            return False
        _LOGGER.debug(
            "ISY command %s sent to %s.", COMMAND_FRIENDLY_NAME.get(cmd), self._id
        )

        # Calculate hint to use if status is updated
        hint = self.status
        if cmd == CMD_ON:
            if val is not None:
                hint = int(val)
            elif PROP_ON_LEVEL in self._aux_properties:
                hint = self._aux_properties[PROP_ON_LEVEL].value
            else:
                hint = 255
        elif cmd == CMD_ON_FAST:
            hint = 255
        elif cmd in [CMD_OFF, CMD_OFF_FAST]:
            hint = 0
        self.update(wait_time=UPDATE_INTERVAL, hint=hint)
        return True

    def beep(self):
        """Identify physical device by sound (if supported)."""
        return self.send_cmd(CMD_BEEP)

    def brighten(self):
        """Increase brightness of a device by ~3%."""
        return self.send_cmd(CMD_BRIGHTEN)

    def dim(self):
        """Decrease brightness of a device by ~3%."""
        return self.send_cmd(CMD_DIM)

    def disable(self):
        """Send command to the node to disable it."""
        if not self.isy.conn.request(
            self.isy.conn.compile_url([URL_NODES, str(self._id), CMD_DISABLE])
        ):
            _LOGGER.warning("ISY could not %s %s.", CMD_DISABLE, self._id)
            return False
        return True

    def enable(self):
        """Send command to the node to enable it."""
        if not self.isy.conn.request(
            self.isy.conn.compile_url([URL_NODES, str(self._id), CMD_ENABLE])
        ):
            _LOGGER.warning("ISY could not %s %s.", CMD_ENABLE, self._id)
            return False
        return True

    def fade_down(self):
        """Begin fading down (dim) a device."""
        return self.send_cmd(CMD_FADE_DOWN)

    def fade_stop(self):
        """Stop fading a device."""
        return self.send_cmd(CMD_FADE_STOP)

    def fade_up(self):
        """Begin fading up (dim) a device."""
        return self.send_cmd(CMD_FADE_UP)

    def fast_off(self):
        """Start manually brightening a device."""
        return self.send_cmd(CMD_OFF_FAST)

    def fast_on(self):
        """Start manually brightening a device."""
        return self.send_cmd(CMD_ON_FAST)

    def query(self):
        """Request the ISY query this node."""
        return self.isy.query(address=self.address)

    def turn_off(self):
        """Turn off the nodes/group in the ISY."""
        return self.send_cmd(CMD_OFF)

    def turn_on(self, val=None):
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
        return self.send_cmd(cmd, val)
