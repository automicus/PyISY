"""Representation of groups (scenes) from an ISY."""
from ..constants import VALUE_UNKNOWN
from .nodebase import NodeBase


class Group(NodeBase):
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

    def __init__(self, nodes, nid, name, members=None, controllers=None):
        """Initialize a Group class."""
        self._members = members or []
        self._controllers = controllers or []
        super().__init__(nodes, nid, name)

        # listen for changes in children
        self._members_handlers = [
            self._nodes[m].status.subscribe("changed", self.update)
            for m in self.members
        ]

        # get and update the status
        self.update()

    def __del__(self):
        """Cleanup event handlers before deleting."""
        for handler in self._members_handlers:
            handler.unsubscribe()

    def __report_status__(self, new_val):
        """Report the status of the scene."""
        # first clean the status input
        status = int(self.status)
        if status > 0:
            clean_status = 255
        elif status <= 0:
            clean_status = 0
        if status != clean_status:
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

    def update(self, wait_time=0, hint=None, xmldoc=None):
        """Update the group with values from the controller."""
        for node in self.members:
            if (
                self._nodes[node].status is None
                or self._nodes[node].status == VALUE_UNKNOWN
            ):
                continue
            elif int(self._nodes[node].status) > 0:
                self.status.update(255, force=True, silent=True)
                return
        self.status.update(0, force=True, silent=True)
