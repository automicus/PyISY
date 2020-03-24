"""Representation of groups (scenes) from an ISY."""
from VarEvents import Property

from ..constants import ISY_VALUE_UNKNOWN, PROTO_GROUP
from .nodebase import NodeBase


class Group(NodeBase):
    """
    Interact with ISY groups (scenes).

    |  nodes: The node manager object.
    |  address: The node ID.
    |  name: The node name.
    |  members: List of the members in this group.
    |  controllers: List of the controllers in this group.
    |  spoken: The string of the Notes Spoken field.

    :ivar has_children: Boolean value indicating that group has no children.
    :ivar members: List of the members of this group.
    :ivar controllers: List of the controllers of this group.
    :ivar name: The name of this group.
    :ivar status: Watched property indicating the status of the group.
    :ivar group_all_on: Watched property indicating if all devices in group are on.
    """

    group_all_on = Property(False)

    def __init__(self, nodes, address, name, members=None, controllers=None):
        """Initialize a Group class."""
        self._members = members or []
        self._controllers = controllers or []
        super().__init__(nodes, address, name, family_id="6")

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
            self.turn_on()
        else:
            self.turn_off()

    @property
    def members(self):
        """Get the members of the scene/group."""
        return self._members

    @property
    def protocol(self):
        """Return the protocol for this entity."""
        return PROTO_GROUP

    @property
    def controllers(self):
        """Get the controller nodes of the scene/group."""
        return self._controllers

    def update(self, wait_time=0, hint=None, xmldoc=None):
        """Update the group with values from the controller."""
        valid_nodes = [
            node
            for node in self.members
            if (
                self._nodes[node].status is not None
                and self._nodes[node].status != ISY_VALUE_UNKNOWN
            )
        ]
        on_nodes = [node for node in valid_nodes if int(self._nodes[node].status) > 0]

        if on_nodes:
            self.group_all_on.update(len(on_nodes) == len(valid_nodes), silent=True)
            self.status.update(255, force=True, silent=True)
            return
        self.status.update(0, force=True, silent=True)
        self.group_all_on.update(False, silent=True)
