"""Representation of groups (scenes) from an ISY."""
from ..constants import ISY_VALUE_UNKNOWN, PROTO_GROUP
from ..helpers import now
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

    def __init__(
        self,
        nodes,
        address,
        name,
        members=None,
        controllers=None,
        family_id="6",
        pnode=None,
    ):
        """Initialize a Group class."""
        self._all_on = False
        self._controllers = controllers or []
        self._members = members or []
        super().__init__(nodes, address, name, 0, family_id=family_id, pnode=pnode)

        # listen for changes in children
        self._members_handlers = [
            self._nodes[m].status_events.subscribe(self.update_callback)
            for m in self.members
        ]

        # get and update the status
        self.isy.loop.create_task(self.update())

    def __del__(self):
        """Cleanup event handlers before deleting."""
        for handler in self._members_handlers:
            handler.unsubscribe()

    @property
    def controllers(self):
        """Get the controller nodes of the scene/group."""
        return self._controllers

    @property
    def group_all_on(self):
        """Return the current node state."""
        return self._all_on

    @group_all_on.setter
    def group_all_on(self, value):
        """Set the current node state and notify listeners."""
        if self._all_on != value:
            self._all_on = value
            self._last_changed = now()
            # Re-publish the current status. Let users pick up the all on change.
            self.status_events.notify(self._status)
        return self._all_on

    @property
    def members(self):
        """Get the members of the scene/group."""
        return self._members

    @property
    def protocol(self):
        """Return the protocol for this entity."""
        return PROTO_GROUP

    async def update(self, event=None, wait_time=0, xmldoc=None):
        """Update the group with values from the controller."""
        self._last_update = now()
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
            self.group_all_on = len(on_nodes) == len(valid_nodes)
            self.status = 255
            return
        self.status = 0
        self.group_all_on = False

    def update_callback(self, event=None):
        """Handle synchronous callbacks for subscriber events."""
        self.isy.loop.create_task(self.update(event))
