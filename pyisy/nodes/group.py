"""Representation of groups (scenes) from an ISY."""
from __future__ import annotations

from ..constants import (
    FAMILY_GENERIC,
    INSTEON_STATELESS_NODEDEFID,
    ISY_VALUE_UNKNOWN,
    PROTO_GROUP,
)
from ..helpers import EventListener, NodeProperty, now
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

    _all_on: bool
    _controllers: list[str]
    _members: list[str]
    _members_handlers: list[EventListener]

    def __init__(
        self,
        nodes,
        address,
        name,
        members=None,
        controllers=None,
        family_id=FAMILY_GENERIC,
        pnode=None,
        flag=0,
    ):
        """Initialize a Group class."""
        self._all_on = False
        self._controllers = controllers or []
        self._members = members or []
        super().__init__(
            nodes, address, name, 0, family_id=family_id, pnode=pnode, flag=flag
        )

        # listen for changes in children
        self._members_handlers = [
            self._nodes[m].status_events.subscribe(self.update_callback)
            for m in self.members
        ]

        # get and update the status
        self._update()

    def __del__(self) -> None:
        """Cleanup event handlers before deleting."""
        for handler in self._members_handlers:
            handler.unsubscribe()

    @property
    def controllers(self) -> list[str]:
        """Get the controller nodes of the scene/group."""
        return self._controllers

    @property
    def group_all_on(self) -> bool:
        """Return the current node state."""
        return self._all_on

    @group_all_on.setter
    def group_all_on(self, value: bool) -> None:
        """Set the current node state and notify listeners."""
        if self._all_on != value:
            self._all_on = value
            self._last_changed = now()
            # Re-publish the current status. Let users pick up the all on change.
            self.status_events.notify(self._status)

    @property
    def members(self) -> list[str]:
        """Get the members of the scene/group."""
        return self._members

    @property
    def protocol(self) -> str:
        """Return the protocol for this entity."""
        return PROTO_GROUP

    async def update(
        self,
        event: NodeProperty | None = None,
        wait_time: float | None = 0,
        xmldoc: str | None = None,
    ) -> None:
        """Update the group with values from the controller."""
        self._update(event, wait_time, xmldoc)

    def _update(
        self,
        event: NodeProperty | None = None,
        wait_time: float | None = 0,
        xmldoc: str | None = None,
    ) -> None:
        """Update the group with values from the controller."""
        self._last_update = now()
        valid_nodes = [
            node
            for node in self.members
            if (
                self._nodes[node].status is not None
                and self._nodes[node].status != ISY_VALUE_UNKNOWN
                and self._nodes[node].node_def_id not in INSTEON_STATELESS_NODEDEFID
            )
        ]
        on_nodes = [node for node in valid_nodes if int(self._nodes[node].status) > 0]
        if on_nodes:
            self.group_all_on = len(on_nodes) == len(valid_nodes)
            self.status = 255
            return
        self.status = 0
        self.group_all_on = False

    def update_callback(self, event: NodeProperty | None = None) -> None:
        """Handle synchronous callbacks for subscriber events."""
        self._update(event)
