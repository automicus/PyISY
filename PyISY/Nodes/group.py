from VarEvents import Property


class Group(object):

    """
    This class interacts with ISY groups (scenes).

    |  parent: The node manager object.
    |  nid: The node ID.
    |  name: The node name.
    |  members: List of the members in this group.
    |  controllers: List of the controllers in this group.
    |  spoken: The string of the Notes Spoken field.

    :ivar dimmable: Boolean value idicating that this group cannot be dimmed.
    :ivar hasChildren: Boolean value indicating that this group has no children.
    :ivar members: List of the members of this group.
    :ivar controllers: List of the controllers of this group.
    :ivar name: The name of this group.
    :ivar status: Watched property indicating the status of the group.
    """

    status = Property(0)
    hasChildren = False

    def __init__(self, parent, nid, name, members=None, controllers=None, notes=False):
        self.parent = parent
        self._id = nid
        self.name = name
        self._members = members or []
        self._controllers = controllers or []
        self.dimmable = False
        self._running = False
        self._notes = notes

        # listen for changes in children
        self._membersHandlers = [
            self.parent[m].status.subscribe('changed', self.update)
            for m in self.members]

        # get and update the status
        self.update()

        # respond to non-silent changes in status
        self.status.reporter = self.__report_status__

    def __del__(self):
        """ Cleanup event handlers before deleting. """
        for handler in self._membersHandlers:
            handler.unsubscribe()

    def __str__(self):
        """ Return a string representation for this group. """
        return 'Group(' + self._id + ')'

    def __report_status__(self, new_val):
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
        return self._members

    @property
    def controllers(self):
        return self._controllers

    def update(self, e=None):
        """ Update the group with values from the controller. """
        for m in self.members:
            if self.parent[m].status == None:
                continue
            elif self.parent[m].status > 0:
                self.status.update(255, force=True, silent=True)
                return
        self.status.update(0, force=True, silent=True)

    def off(self):
        """Turns off all the nodes in a scene."""
        response = self.parent.parent.conn.nodeOff(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not turn off scene: ' +
                                           self._id)
            return False
        else:
            self.parent.parent.log.info('ISY turned off scene: ' + self._id)
            return True

    def on(self):
        """Turns on all the nodes in the scene to the set values."""
        response = self.parent.parent.conn.nodeOn(self._id, None)

        if response is None:
            self.parent.parent.log.warning('ISY could not turn on scene: ' +
                                           self._id)
            return False
        else:
            self.parent.parent.log.info('ISY turned on scene: ' + self._id)
            return True

    def _get_notes(self):
        #if not self._notes:
        self._notes = self.parent.parseNotes(self.parent.parent.conn.getNodeNotes(self._id))

    @property
    def spoken(self):
        """Returns the text string of the Spoken property inside the group notes"""
        self._get_notes()
        return self._notes['spoken']
