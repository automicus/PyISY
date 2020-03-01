"""Base object for nodes and groups."""
from xml.dom import minidom

from VarEvents import Property

from ..constants import COMMAND_FRIENDLY_NAME, UPDATE_INTERVAL, XML_PARSE_ERROR
from ..helpers import value_from_xml


class NodeBase:
    """Base Object for Nodes and Groups/Scenes."""

    status = Property(0)
    hasChildren = False

    def __init__(self, nodes, nid, name):
        """Initialize a Group class."""
        self._nodes = nodes
        self.isy = nodes.isy
        self._id = nid
        self._name = name
        self._notes = None

        # respond to non-silent changes in status
        self.status.reporter = self.__report_status__

    def __str__(self):
        """Return a string representation of the node."""
        return '{}({})'.format(type(self).__name__, self._id)

    @property
    def nid(self):
        """Return the Node ID."""
        return self._id

    @property
    def name(self):
        """Return the name of the Node."""
        return self._name

    def parse_notes(self):
        """Parse the notes for a given node."""
        notes_xml = self.isy.conn.request(
            self.isy.conn.compile_url(['nodes', self._id, 'notes']),
            ok404=True)
        spoken = None
        if notes_xml is not None and notes_xml != "":
            try:
                notesdom = minidom.parseString(notes_xml)
            except:
                self.isy.log.error("%s: Node Notes %s",
                                   XML_PARSE_ERROR, notes_xml)
            else:
                spoken = value_from_xml(notesdom, 'spoken')
        return {"spoken": spoken}

    @property
    def spoken(self):
        """Return the text of the Spoken property inside the group notes."""
        self._notes = self.parse_notes()
        return self._notes["spoken"]

    def __report_status__(self, new_val):
        """Report the status of the node."""
        self.on(new_val)

    def off(self):
        """Turn off the nodes/group in the ISY."""
        return self.send_cmd('DOF')

    def on(self, val=None):
        """
        Turn the node on.

        |  [optional] val: The value brightness value (0-255) for the node.
        """
        if val is None or type(self).__name__ == "Group":
            cmd = 'DON'
        elif int(val) > 0:
            cmd = 'DON'
            val = str(val) if int(val) < 255 else None
        else:
            cmd = 'DOF'
            val = None
        return self.send_cmd(cmd, val)

    def update(self, wait_time=0, hint=None, xmldoc=None):
        """Update the group with values from the controller."""
        pass

    def send_cmd(self, cmd, val=None):
        """Send a command to the device."""
        value = str(val) if val is not None else None
        req = ['nodes', str(self._id), 'cmd', cmd]
        if value:
            req.append(value)
        req_url = self.isy.conn.compile_url(req)
        if not self.isy.conn.request(req_url):
            self.isy.log.warning('ISY could not send %s command to %s.',
                                 COMMAND_FRIENDLY_NAME.get(cmd), self._id)
            return False
        self.isy.log.info('ISY command %s sent to %s.',
                          COMMAND_FRIENDLY_NAME.get(cmd), self._id)

        # Calculate hint to use if status is updated
        hint = None
        if cmd in ['DON', 'DFON']:
            hint = val if val is not None else 255
        if cmd in ['DOF', 'DFOF']:
            hint = 0

        self.update(UPDATE_INTERVAL, hint=hint)
        return True
