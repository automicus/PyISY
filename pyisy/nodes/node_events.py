"""Event handlers for ISY Nodes."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, cast

from pyisy.constants import TAG_ENABLED, NodeChangeAction
from pyisy.helpers.events import NodeChangedEvent
from pyisy.logging import _LOGGER
from pyisy.nodes.node import Node

if TYPE_CHECKING:
    from pyisy.events.router import EventData
    from pyisy.nodes import Nodes


PLATFORM = "nodes"


MEMORY_REGEX = (
    r".*dbAddr=(?P<dbAddr>[A-F0-9x]*) \[(?P<value>[A-F0-9]{2})\] "
    r"cmd1=(?P<cmd1>[A-F0-9x]{4}) cmd2=(?P<cmd2>[A-F0-9x]{4})"
)


async def node_update_received(nodes: Nodes, event: EventData) -> None:
    """Update nodes from event stream message."""
    if (address := cast(str, event.node)) not in nodes.addresses:
        # New/unknown node, get the details and add
        _LOGGER.debug("Fetching information for new node %s", address)
        await nodes.update_node(address)
        return
    entity = cast(Node, nodes.entities[address])
    if not isinstance((action := event.action), dict) or not action:
        return
    # Merge control into action to match status call
    action["control"] = event.control
    await nodes.parse_node_properties(action, entity)


async def node_changed_received(nodes: Nodes, event: EventData) -> None:
    """Handle Node Change/Update events from an event stream message."""
    action: str = cast(str, event.action)
    try:
        description = NodeChangeAction(action).name
    except ValueError:
        description = action

    address: str = cast(str, event.node)
    detail: dict = cast(dict, event.event_info)

    if action == NodeChangeAction.NODE_ERROR:
        _LOGGER.error("ISY Could not communicate with device: %s", address)
    elif action == NodeChangeAction.NODE_ENABLED and address in nodes.addresses:
        if detail and TAG_ENABLED in detail:
            entity = nodes.entities[address]
            entity.update_enabled(cast(bool, detail[TAG_ENABLED]))

    nodes.status_events.notify(event=NodeChangedEvent(address, action, detail))
    _LOGGER.debug(
        "Received a %s event for node %s %s",
        description.replace("_", " ").title(),
        address,
        detail if detail else "",
    )
    # FUTURE: Handle additional node change actions to force updates.


async def progress_report_received(nodes: Nodes, event_data: EventData) -> None:
    """Handle Progress Report '_7' events from an event stream message."""
    address, _, message = cast(str, event_data.event_info).partition("]")
    address = address.strip("[ ")
    message = message.strip()
    action = NodeChangeAction.DEVICE_WRITING
    detail: dict[str, str | int] = {"message": message}

    if address != "All" and message.startswith("Memory"):
        action = NodeChangeAction.DEVICE_MEMORY
        regex = re.compile(MEMORY_REGEX)
        if event := regex.search(message):
            detail = {
                "memory": event.group("dbAddr"),
                "cmd1": event.group("cmd1"),
                "cmd2": event.group("cmd2"),
                "value": int(event.group("value"), 16),
            }
    nodes.status_events.notify(event=NodeChangedEvent(address, action, detail))
    _LOGGER.debug(
        "Received a progress report %s event for node %s %s",
        action,
        address,
        detail if detail else "",
    )
