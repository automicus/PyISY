"""Base object for nodes and groups."""
from xml.dom import minidom

from VarEvents import Property

from ..constants import (
    CMD_BEEP,
    CMD_BRIGHTEN,
    CMD_DIM,
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
    TAG_SPOKEN,
    UPDATE_INTERVAL,
    URL_NODES,
    URL_NOTES,
    XML_PARSE_ERROR,
)
from ..helpers import value_from_xml


class NodeBase:
    """Base Object for Nodes and Groups/Scenes."""

    status = Property(0)
    has_children = False

    def __init__(
        self, nodes, address, name, family_id=None, aux_properties=None, pnode=None
    ):
        """Initialize a Group class."""
        self._nodes = nodes
        self.isy = nodes.isy
        self._id = address
        self._name = name
        self._notes = None
        self._primary_node = pnode
        self._aux_properties = aux_properties if aux_properties is not None else {}
        self._family = NODE_FAMILY_ID.get(family_id)

        # respond to non-silent changes in status
        self.status.reporter = self.__report_status__

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
    def name(self):
        """Return the name of the Node."""
        return self._name

    @property
    def family(self):
        """Return the ISY Family category."""
        return self._family

    def parse_notes(self):
        """Parse the notes for a given node."""
        notes_xml = self.isy.conn.request(
            self.isy.conn.compile_url([URL_NODES, self._id, URL_NOTES]), ok404=True
        )
        spoken = None
        if notes_xml is not None and notes_xml != "":
            try:
                notesdom = minidom.parseString(notes_xml)
            except (AttributeError, KeyError, ValueError, TypeError, IndexError):
                self.isy.log.error("%s: Node Notes %s", XML_PARSE_ERROR, notes_xml)
            else:
                spoken = value_from_xml(notesdom, TAG_SPOKEN)
        return {TAG_SPOKEN: spoken}

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
        self._notes = self.parse_notes()
        return self._notes[TAG_SPOKEN]

    def __report_status__(self, new_val):
        """Report the status of the node."""
        self.turn_on(new_val)

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

    def update(self, wait_time=0, hint=None, xmldoc=None):
        """Update the group with values from the controller."""
        pass

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
            self.isy.log.warning(
                "ISY could not send %s command to %s.",
                COMMAND_FRIENDLY_NAME.get(cmd),
                self._id,
            )
            return False
        self.isy.log.debug(
            "ISY command %s sent to %s.", COMMAND_FRIENDLY_NAME.get(cmd), self._id
        )

        # Calculate hint to use if status is updated
        # pylint: disable=protected-access
        hint = self.status._val
        if cmd == CMD_ON:
            if val is not None:
                hint = val
            elif PROP_ON_LEVEL in self._aux_properties:
                hint = self._aux_properties[PROP_ON_LEVEL].value
            else:
                hint = 255
        elif cmd == CMD_ON_FAST:
            hint = 255
        elif cmd in [CMD_OFF, CMD_OFF_FAST]:
            hint = 0
        self.update(UPDATE_INTERVAL, hint=hint)
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

    def fade_down(self):
        """Begin fading down (dim) a device."""
        return self.send_cmd(CMD_FADE_DOWN)

    def fade_up(self):
        """Begin fading up (dim) a device."""
        return self.send_cmd(CMD_FADE_UP)

    def fade_stop(self):
        """Stop fading a device."""
        return self.send_cmd(CMD_FADE_STOP)

    def fast_on(self):
        """Start manually brightening a device."""
        return self.send_cmd(CMD_ON_FAST)

    def fast_off(self):
        """Start manually brightening a device."""
        return self.send_cmd(CMD_OFF_FAST)
