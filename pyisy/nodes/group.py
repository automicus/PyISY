"""Representation of groups (scenes) from an ISY."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, cast

from pyisy.constants import (
    INSTEON_STATELESS_NODEDEFID,
    ISY_VALUE_UNKNOWN,
    NODE_IS_CONTROLLER,
    Protocol,
)
from pyisy.helpers.entity import Entity
from pyisy.helpers.events import EventListener
from pyisy.helpers.models import NodeProperty
from pyisy.nodes.nodebase import NodeBase, NodeBaseDetail

if TYPE_CHECKING:
    from pyisy.nodes import Nodes


@dataclass
class GroupDetail(NodeBaseDetail):
    """Dataclass to hold group details."""

    device_group: str = ""
    members: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    links: list[str] = field(init=False, default_factory=list)
    controllers: list[str] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        """Post-initialize the GroupDetail dataclass."""
        if not self.members:
            return

        # Get the link list and make single links a dict
        link_list: list[dict[str, str]] | dict[str, str] = self.members.get("link", [])
        if not (link_list):
            return
        if isinstance(link_list, dict):
            link_list = [link_list]

        for link in link_list:
            address = link["address"]
            self.links.append(address)
            if int(link["type_"]) == NODE_IS_CONTROLLER:
                self.controllers.append(address)


class Group(NodeBase, Entity):
    """Interact with ISY groups (scenes)."""

    _all_on: bool
    _members_handlers: list[EventListener]
    detail: GroupDetail
    platform: Nodes

    def __init__(
        self,
        platform: Nodes,
        address: str,
        name: str,
        detail: GroupDetail,
    ):
        """Initialize a Group class."""
        self._protocol = Protocol.GROUP
        self._all_on = False
        super().__init__(platform=platform, address=address, name=name, detail=detail)

        # listen for changes in children
        self._members_handlers = [
            self.platform.entities[m].status_events.subscribe(self.update_callback)
            for m in self.detail.links
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
        return self.detail.controllers

    @property
    def group_all_on(self) -> bool:
        """Return the current node state."""
        return self._all_on

    @group_all_on.setter
    def group_all_on(self, value: bool) -> None:
        """Set the current node state and notify listeners."""
        if self._all_on != value:
            self._all_on = value
            self._last_changed = datetime.now()
            # Re-publish the current status. Let users pick up the all on change.
            self.status_events.notify(self._status)

    @property
    def members(self) -> list[str]:
        """Get the members of the scene/group."""
        return self.detail.links

    # async def update(
    #     self,
    #     event: NodeProperty | None = None,
    #     wait_time: float | None = 0,
    #     xmldoc: str | None = None,
    # ) -> None:
    #     """Update the group with values from the controller."""
    #     self._update(event, wait_time, xmldoc)

    def _update(
        self,
    ) -> None:
        """Update the group with values from the controller."""
        self._last_update = datetime.now()

        valid_nodes = []
        for address in self.members:
            node = self.platform.entities[address]
            if (
                node.status is not None
                and node.status != ISY_VALUE_UNKNOWN
                and cast(NodeBaseDetail, node.detail).node_def_id
                not in INSTEON_STATELESS_NODEDEFID
            ):
                valid_nodes.append(address)
        on_nodes = [
            node for node in valid_nodes if int(self.platform.entities[node].status) > 0
        ]
        if on_nodes:
            self.group_all_on = len(on_nodes) == len(valid_nodes)
            self.update_status(255)
            return
        self.update_status(0)
        self.group_all_on = False

    def update_callback(self, event: NodeProperty | None = None) -> None:
        """Handle synchronous callbacks for subscriber events."""
        self._update()
