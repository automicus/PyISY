"""Representation of groups (scenes) from an ISY."""
from VarEvents import Property


class Group:
    """
    Interact with ISY groups (scenes).

    |  nodes: The node manager object.
    |  nid: The node ID.
    |  name: The node name.
    |  members: List of the members in this group.
    |  controllers: List of the controllers in this group.
    |  spoken: The string of the Notes Spoken field.

    :ivar hasChildren: Boolean value indicating that group has no children.
    :ivar members: List of the members of this group.
    :ivar controllers: List of the controllers of this group.
    :ivar name: The name of this group.
    :ivar status: Watched property indicating the status of the group.
    """

    status = Property(0)
    hasChildren = False

    def __init__(self, nodes, nid, name, members=None,
                 controllers=None, notes=False):
        """Initialize a Group class."""
        self._nodes = nodes
        self.isy = nodes.isy
        self._id = nid
        self.name = name
        self._members = members or []
        self._controllers = controllers or []
        self._running = False
        self._notes = notes

        # listen for changes in children
        self._members_handlers = [
            self._nodes[m].status.subscribe('changed', self.update)
            for m in self.members]

        # get and update the status
        self.update()

        # respond to non-silent changes in status
        self.status.reporter = self.__report_status__

    def __del__(self):
        """ Cleanup event handlers before deleting."""
        for handler in self._members_handlers:
            handler.unsubscribe()

    def __str__(self):
        """ Return a string representation for this group."""
        return 'Group(' + self._id + ')'

    def __report_status__(self, new_val):
        """Report the status of the scene."""
        # first clean the status input
        if self.status > 0:
            clean_status = 255
        elif self.status <= 0:
            clean_status = 0
        if self.status != clean_status:
            self.status.update(clean_status, force=True, silent=True)

        # now update the nodes
        if clean_status > 0:
            self.on()
        else:
            self.off()

    @property
    def members(self):
        """Get the members of the scene/group."""
        return self._members

    @property
    def controllers(self):
        """Get the controller nodes of the scene/group."""
        return self._controllers

    def update(self, err=None):
        """Update the group with values from the controller."""
        for node in self.members:
            if self._nodes[node].status is None:
                continue
            elif self._nodes[node].status > 0:
                self.status.update(255, force=True, silent=True)
                return
        self.status.update(0, force=True, silent=True)

    def off(self):
        """Turn off all nodes in a scene."""
        if not self.isy.conn.node_send_cmd(self._id, 'DOF'):
            self.isy.log.warning('ISY could not turn off scene: ' + self._id)
            return False
        self.isy.log.info('ISY turned off scene: ' + self._id)
        return True

    def on(self):
        """Turn off all nodes in a scene."""
        if not self.isy.conn.node_send_cmd(self._id, 'DON'):
            self.isy.log.warning('ISY could not turn on scene: ' + self._id)
            return False
        self.isy.log.info('ISY turned on scene: ' + self._id)
        return True

    @property
    def spoken(self):
        """Return the text of the Spoken property inside the group notes."""
        self._notes = self._nodes.parse_notes(self._id)
        return self._notes['spoken']
