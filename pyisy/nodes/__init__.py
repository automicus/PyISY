"""Representation of ISY Nodes."""
from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING, cast, Any
import json
from xml.dom import minidom

from pyisy.constants import (
    ATTR_ACTION,
    ATTR_CONTROL,
    ATTR_FLAG,
    ATTR_ID,
    ATTR_INSTANCE,
    ATTR_NODE_DEF_ID,
    ATTR_PRECISION,
    ATTR_UNIT_OF_MEASURE,
    DEFAULT_PRECISION,
    DEFAULT_UNIT_OF_MEASURE,
    DEV_MEMORY,
    DEV_WRITING,
    EVENT_PROPS_IGNORED,
    FAMILY_BRULTECH,
    FAMILY_NODESERVER,
    FAMILY_RCS,
    FAMILY_ZMATTER_ZWAVE,
    FAMILY_ZWAVE,
    INSTEON_RAMP_RATES,
    ISY_VALUE_UNKNOWN,
    NC_NODE_ENABLED,
    NC_NODE_ERROR,
    NODE_CHANGED_ACTIONS,
    NODE_IS_CONTROLLER,
    NODE_IS_ROOT,
    PROP_BATTERY_LEVEL,
    PROP_COMMS_ERROR,
    PROP_RAMP_RATE,
    PROP_STATUS,
    PROTO_INSTEON,
    PROTO_NODE_SERVER,
    PROTO_ZIGBEE,
    PROTO_ZWAVE,
    TAG_ADDRESS,
    TAG_DEVICE_TYPE,
    TAG_ENABLED,
    TAG_EVENT_INFO,
    TAG_FAMILY,
    TAG_FOLDER,
    TAG_FORMATTED,
    TAG_GROUP,
    TAG_LINK,
    TAG_NAME,
    TAG_NODE,
    TAG_PARENT,
    TAG_PRIMARY_NODE,
    TAG_TYPE,
    UOM_SECONDS,
    XML_TRUE,
    URL_NODES,
    URL_STATUS,
)
from pyisy.exceptions import XML_ERRORS, XML_PARSE_ERROR, ISYResponseParseError
from pyisy.helpers.events import EventEmitter, NodeChangedEvent
from pyisy.helpers.entity_platform import EntityPlatform
from pyisy.events.router import EventData
from pyisy.helpers.models import NodeProperty, ZWaveProperties
from pyisy.helpers.xml import (
    attr_from_element,
    attr_from_xml,
    value_from_xml,
    parse_xml,
)
from pyisy.logging import _LOGGER, LOG_VERBOSE
from pyisy.node_servers import NodeServers
from pyisy.nodes.group import Group, GroupDetail
from pyisy.nodes.node import Node, NodeDetail
from pyisy.nodes.parser import parse_xml_properties
from pyisy.nodes.folder import NodeFolderDetail, NodeFolder

if TYPE_CHECKING:
    from pyisy.isy import ISY

PLATFORM = "nodes"

MEMORY_REGEX = (
    r".*dbAddr=(?P<dbAddr>[A-F0-9x]*) \[(?P<value>[A-F0-9]{2})\] "
    r"cmd1=(?P<cmd1>[A-F0-9x]{4}) cmd2=(?P<cmd2>[A-F0-9x]{4})"
)


class Nodes(EntityPlatform):
    """This class handles the ISY nodes."""

    node_servers: set = set()

    def __init__(
        self,
        isy: ISY,
    ) -> None:
        """Initialize the Nodes ISY Node Manager class.

        Iterate over self.values()
        """
        super().__init__(isy=isy, platform_name=PLATFORM)
        self.status_events = EventEmitter()
        self.url = self.isy.conn.compile_url([URL_NODES])
        self.status_url = self.isy.conn.compile_url([URL_STATUS])
        self._parse_cdata_key = "address"

    async def parse(self, xml_dict: dict[str, Any]) -> None:
        """Parse the results from the ISY."""
        # Write nodes to file for debugging:
        # json_object = json.dumps(xml_dict, indent=4, default=str)
        # with open("nodes.json", "w", encoding="utf-8") as outfile:
        #     outfile.write(json_object)

        if not (features := xml_dict["nodes"]):
            return

        if folders := features["folder"]:
            for folder in folders:
                await self.parse_folder_entity(folder)
        if nodes := features["node"]:
            for node in nodes:
                await self.parse_node_entity(node)
        if groups := features["group"]:
            for group in groups:
                await self.parse_group_entity(group)

        await self.update_status()
        _LOGGER.info("Loaded %s", PLATFORM)
        # if self.isy.node_servers is None:
        #     self.isy.node_servers = NodeServers(self.isy, set(node_servers))

    async def parse_folder_entity(self, feature: dict[str, Any]) -> None:
        """Parse a single folder and add to the platform."""
        try:
            address = feature["address"]
            name = feature["name"]
            _LOGGER.log(LOG_VERBOSE, "Parsing %s: %s (%s)", PLATFORM, name, address)
            entity = NodeFolder(self, address, name, NodeFolderDetail(**feature))
            await self.add_or_update_entity(address, name, entity)
        except (TypeError, KeyError, ValueError) as exc:
            _LOGGER.exception("Error loading %s: %s", PLATFORM, exc)

    async def parse_node_entity(self, feature: dict[str, Any]) -> None:
        """Parse a single node and add to the platform."""
        try:
            address = feature["address"]
            name = feature["name"]
            _LOGGER.log(LOG_VERBOSE, "Parsing %s: %s (%s)", PLATFORM, name, address)
            feature["protocol"] = await self.get_protocol_from_family(
                feature.get("family")
            )
            #     state, aux_props, state_set = parse_xml_properties(feature)
            entity = Node(self, address, name, NodeDetail(**feature))
            await self.add_or_update_entity(address, name, entity)
        except (TypeError, KeyError, ValueError) as exc:
            _LOGGER.exception("Error loading %s: %s", PLATFORM, exc)

    async def parse_group_entity(self, feature: dict[str, Any]) -> None:
        """Parse a single group and add to the platform."""
        try:
            address = feature["address"]
            name = feature["name"]
            _LOGGER.log(LOG_VERBOSE, "Parsing %s: %s (%s)", PLATFORM, name, address)
            if (flag := feature["flag"]) & NODE_IS_ROOT:
                _LOGGER.debug("Skipping root group flag=%s %s", flag, address)
                return
            entity = Group(self, address, name, GroupDetail(**feature))
            await self.add_or_update_entity(address, name, entity)
        except (TypeError, KeyError, ValueError) as exc:
            _LOGGER.exception("Error loading %s: %s", PLATFORM, exc)

    async def get_protocol_from_family(
        self, family: str | dict[str, str] | None
    ) -> str:
        """Identify protocol from family type."""
        if family is None:
            return PROTO_INSTEON
        if isinstance(family, dict) and family["address"] == FAMILY_NODESERVER:
            node_server = family.get("instance", "")
            self.node_servers.add(node_server)
            return f"{PROTO_NODE_SERVER}_{node_server}"
        if family in (FAMILY_ZWAVE, FAMILY_ZMATTER_ZWAVE):
            return PROTO_ZWAVE
        if family in (FAMILY_BRULTECH, FAMILY_RCS):
            return PROTO_ZIGBEE
        return PROTO_INSTEON

    async def update_status(self, wait_time: float = 0) -> None:
        """Update the contents of the class from the status endpoint."""
        await asyncio.sleep(wait_time)
        xml_dict = parse_xml(
            await self.isy.conn.request(self.status_url),
            attr_prefix=self._parse_attr_prefix,
            cdata_key=self._parse_cdata_key,
            use_pp=self._parse_use_pp,
        )
        _LOGGER.log(
            LOG_VERBOSE,
            "%s:\n%s",
            self.url,
            json.dumps(xml_dict, indent=4, sort_keys=True, default=str),
        )
        await self.parse_status(xml_dict)

    async def parse_status(self, xml_dict: dict[str, Any]) -> None:
        """Parse the results from the ISY."""
        # Write nodes to file for debugging:
        # json_object = json.dumps(xml_dict, indent=4, default=str)
        # with open("nodes-status.json", "w", encoding="utf-8") as outfile:
        #     outfile.write(json_object)

        if not (node_statuses := xml_dict["nodes"]["node"]):
            return

        for status in node_statuses:
            await self.parse_node_status(status)

    async def parse_node_status(self, status: dict[str, Any]) -> None:
        """Parse the node status results from the ISY."""
        if (address := status["id"]) not in self.addresses:
            return  # FUTURE: Missing address, go get.
        try:
            if not (props := status["prop"]):
                return
            if isinstance(props, dict):
                props = [props]
            entity: Node = cast(Node, self.entities[address])
            for prop in props:
                result = NodeProperty(**prop)
                if result.control == PROP_STATUS:
                    entity.update_state(result)
                elif result.control == PROP_RAMP_RATE:
                    result.value = INSTEON_RAMP_RATES.get(
                        str(result.value), result.value
                    )
                    result.uom = UOM_SECONDS
                entity.aux_properties[result.control] = result

        except (TypeError, KeyError, ValueError) as exc:
            _LOGGER.exception("Error loading node status (%s): %s", address, exc)

    async def parse_node_property(self, status: dict[str, Any]) -> None:
        """Parse the node node property from the ISY."""

    async def update_received(self, event: EventData) -> None:
        """Update nodes from event stream message."""
        event_info = cast(dict, event.event_info)
        if (address := cast(str, event.node)) not in self.addresses:
            # New/unknown program, refresh full set.
            await self.update()
            return
        entity = self.entities[address]
        detail = entity.detail

        # TODO: Stopped here

        value_str = value_from_xml(xmldoc, ATTR_ACTION, "")
        value = int(value_str) if value_str.strip() != "" else ISY_VALUE_UNKNOWN
        prec = attr_from_xml(xmldoc, ATTR_ACTION, ATTR_PRECISION, DEFAULT_PRECISION)
        uom = attr_from_xml(
            xmldoc, ATTR_ACTION, ATTR_UNIT_OF_MEASURE, DEFAULT_UNIT_OF_MEASURE
        )
        formatted = value_from_xml(xmldoc, TAG_FORMATTED)

        # Process the action and value if provided in event data.
        node.update_state(
            NodeProperty(PROP_STATUS, value, prec, uom, formatted, address)
        )
        _LOGGER.debug("ISY Updated Node: %s", address)

    def control_message_received(self, event: EventData) -> None:
        """
        Pass Control events from an event stream message to nodes.

        Used for sending out to subscribers.
        """
        address = value_from_xml(xmldoc, TAG_NODE)
        cntrl = value_from_xml(xmldoc, ATTR_CONTROL)
        if not (address and cntrl):
            # If there is no node associated with the control message ignore it
            return

        node = self.get_by_id(address)
        if not node:
            _LOGGER.debug(
                "Received a node update for node %s but could not find a record of this "
                "node. Please try restarting the module if the problem persists, this "
                "may be due to a new node being added to the ISY since last restart.",
                address,
            )
            return

        # Process the action and value if provided in event data.
        node.update_last_update()
        value_str = value_from_xml(xmldoc, ATTR_ACTION, "0")
        value = int(value_str) if value_str.strip() != "" else ISY_VALUE_UNKNOWN
        prec = attr_from_xml(xmldoc, ATTR_ACTION, ATTR_PRECISION, DEFAULT_PRECISION)
        uom = attr_from_xml(
            xmldoc, ATTR_ACTION, ATTR_UNIT_OF_MEASURE, DEFAULT_UNIT_OF_MEASURE
        )
        formatted = value_from_xml(xmldoc, TAG_FORMATTED)

        if cntrl == PROP_RAMP_RATE:
            value = INSTEON_RAMP_RATES.get(value_str, value)
            uom = UOM_SECONDS
        node_property = NodeProperty(cntrl, value, prec, uom, formatted, address)
        if (
            cntrl == PROP_COMMS_ERROR
            and value == 0
            and PROP_COMMS_ERROR in node.aux_properties
        ):
            # Clear a previous comms error
            del node.aux_properties[PROP_COMMS_ERROR]
        if cntrl == PROP_BATTERY_LEVEL and node.is_battery_node:
            # Update the state if this is a battery node
            node.update_state(
                NodeProperty(PROP_STATUS, value, prec, uom, formatted, address)
            )
            _LOGGER.debug("ISY Updated Node: %s", address)
        elif cntrl not in EVENT_PROPS_IGNORED:
            node.update_property(node_property)
        node.control_events.notify(node_property)
        _LOGGER.debug("ISY Node Control Event: %s", node_property)

    def node_changed_received(self, event: EventData) -> None:
        """Handle Node Change/Update events from an event stream message."""
        if (action := event.action) not in NODE_CHANGED_ACTIONS:
            return
        (event_desc, e_i_keys) = NODE_CHANGED_ACTIONS[action]
        node = event.node
        detail = {}
        # TODO: this is already a dict now, use it.
        if e_i_keys and event.event_info:
            detail = {key: value_from_xml(xmldoc, key) for key in e_i_keys}

        if action == NC_NODE_ERROR:
            _LOGGER.error("ISY Could not communicate with device: %s", node)
        elif action == NC_NODE_ENABLED and node in self.addresses:
            node_obj: Node = self.get_by_id(node)
            # pylint: disable=attribute-defined-outside-init
            node_obj.enabled = detail[TAG_ENABLED] == XML_TRUE

        self.status_events.notify(event=NodeChangedEvent(node, action, detail))
        _LOGGER.debug(
            "ISY received a %s event for node %s %s",
            event_desc,
            node,
            detail if detail else "",
        )
        # FUTURE: Handle additional node change actions to force updates.

    def progress_report_received(self, event_data: EventData) -> None:
        """Handle Progress Report '_7' events from an event stream message."""
        # TODO: Validate this
        address, _, message = event_data.event_info.partition("]")
        address = address.strip("[ ")
        message = message.strip()
        action = DEV_WRITING
        detail = {"message": message}

        if address != "All" and message.startswith("Memory"):
            action = DEV_MEMORY
            regex = re.compile(MEMORY_REGEX)
            if event := regex.search(event_data.event_info):
                detail = {
                    "memory": event.group("dbAddr"),
                    "cmd1": event.group("cmd1"),
                    "cmd2": event.group("cmd2"),
                    "value": int(event.group("value"), 16),
                }
        self.status_events.notify(event=NodeChangedEvent(address, action, detail))
        _LOGGER.debug(
            "ISY received a progress report %s event for node %s %s",
            action,
            address,
            detail if detail else "",
        )

    async def update_nodes(self, wait_time: float = 0) -> None:
        """
        Update the contents of the class.

        This calls the "/rest/nodes" endpoint.

        |  wait_time: [optional] Amount of seconds to wait before updating
        """
        if wait_time:
            await asyncio.sleep(wait_time)
        xml = await self.isy.conn.get_nodes()
        if xml is None:
            _LOGGER.warning("ISY Failed to update nodes.")
            return
        self.parse(xml)

    def get_folder(self, address: str) -> str:
        """Return the folder of a given node address."""


#         parent = self.nparents[self.addresses.index(address)]
#         if parent is None:
#             # Node is in the root folder.
#             return None
#         parent_index = self.addresses.index(parent)
#         if self.ntypes[parent_index] != TAG_FOLDER:
#             return self.get_folder(parent)
#         return cast(str, self.nnames[parent_index])

#     @property
#     def children(self):
#         """Return the children of the class."""
#         return self.get_children()

#     def get_children(self, ident=None):
#         """Return the children of the class."""
#         if ident is None:
#             ident = self.root
#         out = [
#             (self.ntypes[i], self.nnames[i], self.addresses[i])
#             for i in [
#                 index for index, parent in enumerate(self.nparents) if parent == ident
#             ]
#         ]
#         return out

#     @property
#     def has_children(self):
#         """Return if the root has children."""
#         return self.root in self.nparents

#     @property
#     def name(self):
#         """Return the name of the root."""
#         if self.root is None:
#             return ""
#         ind = self.addresses.index(self.root)
#         return self.nnames[ind]

#     @property
#     def all_lower_nodes(self):
#         """Return all nodes below the current root."""
#         output = []
#         myname = self.name + "/"

#         for dtype, name, ident in self.children:
#             if dtype in [TAG_GROUP, TAG_NODE]:
#                 output.append((dtype, myname + name, ident))
#                 if dtype == TAG_NODE and ident in self.nparents:
#                     output += [
#                         (child[0], f"{myname}{name}/{child[1]}", child[2])
#                         for child in self.get_children(ident)
#                     ]
#             if dtype == TAG_FOLDER:
#                 output += [
#                     (dtype2, myname + name2, ident2)
#                     for (dtype2, name2, ident2) in self[ident].all_lower_nodes
#                 ]
#         return output


# class NodeIterator:
#     """Iterate through a list of nodes, returning node objects."""

#     def __init__(self, nodes, iter_data, delta=1):
#         """Initialize a NodeIterator class."""
#         self.platform = nodes
#         self._iterdata = iter_data
#         self._len = len(iter_data)
#         self._delta = delta

#         if delta > 0:
#             self._ind = 0
#         else:
#             self._ind = self._len - 1

#     def __next__(self):
#         """Get the next element in the iteration."""
#         if self._ind >= self._len or self._ind < 0:
#             raise StopIteration
#         _, path, ident = self._iterdata[self._ind]
#         self._ind += self._delta
#         return (path, self.platform[ident])

#     def __len__(self):
#         """Return the number of elements."""
#         return self._len
