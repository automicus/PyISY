"""Representation of ISY Nodes."""
from __future__ import annotations

import asyncio
from dataclasses import asdict
import json
from typing import TYPE_CHECKING, Any, Union, cast

from pyisy.constants import (
    DEFAULT_DIR,
    EVENT_PROPS_IGNORED,
    INSTEON_RAMP_RATES,
    NODE_IS_ROOT,
    PROP_BATTERY_LEVEL,
    PROP_RAMP_RATE,
    PROP_STATUS,
    TAG_ADDRESS,
    TAG_FOLDER,
    TAG_GROUP,
    TAG_NODE,
    UOM_SECONDS,
    URL_NODES,
    URL_STATUS,
    NodeFamily,
    Protocol,
    UDHierarchyNodeType,
)
from pyisy.helpers.entity_platform import EntityPlatform
from pyisy.helpers.events import EventEmitter
from pyisy.helpers.models import NodeProperty
from pyisy.helpers.xml import parse_xml
from pyisy.logging import _LOGGER, LOG_VERBOSE
from pyisy.nodes.folder import NodeFolder, NodeFolderDetail
from pyisy.nodes.group import Group, GroupDetail
from pyisy.nodes.node import Node, NodeDetail
from pyisy.util.output import write_to_file

if TYPE_CHECKING:
    from pyisy.isy import ISY

PLATFORM = "nodes"

TAG_PROPERTIES = "properties"

NodesT = Union[NodeFolder, Node, Group]


class Nodes(EntityPlatform[NodesT]):
    """This class handles the ISY nodes."""

    node_servers: set = set()
    initialized: bool = False
    status_info: dict = {}
    _parse_raise_on_error: bool = True

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
        self._parse_cdata_key = TAG_ADDRESS

    async def initialize(self) -> None:
        """Initialize the node entities.

        Nodes require two loading steps, loading nodes and loading status.
        """
        if self.loaded and self.initialized:
            return
        # Step 1: Get status (takes longest to download)
        status_task = asyncio.create_task(self.update_status())

        # Step 2: Get and parse nodes
        nodes_task = asyncio.create_task(self.update())

        # Step 3: Parse status into nodes
        # update_status will wait for update to finish

        await nodes_task
        await status_task
        _LOGGER.info("Initialized nodes with status")

    def parse(self, xml_dict: dict[str, Any]) -> None:
        """Parse the results from the ISY."""
        if not (features := xml_dict["nodes"]):
            return

        if folders := features[TAG_FOLDER]:
            for folder in folders:
                self.parse_folder_entity(folder)
        if nodes := features[TAG_NODE]:
            for node in nodes:
                self.parse_node_entity(node)
        if groups := features[TAG_GROUP]:
            for group in groups:
                self.parse_group_entity(group)

        _LOGGER.info("Loaded %s", PLATFORM)

    def parse_folder_entity(self, feature: dict[str, Any]) -> None:
        """Parse a single folder and add to the platform."""
        try:
            address = feature[TAG_ADDRESS]
            name = feature["name"]
            _LOGGER.log(LOG_VERBOSE, "Parsing %s: %s (%s)", PLATFORM, name, address)
            entity = NodeFolder(self, address, name, NodeFolderDetail(**feature))
            self.add_or_update_entity(address, name, entity)
        except (TypeError, KeyError, ValueError) as exc:
            _LOGGER.exception("Error loading %s: %s", PLATFORM, exc)

    def parse_node_entity(self, feature: dict[str, Any]) -> None:
        """Parse a single node and add to the platform."""
        try:
            address = feature[TAG_ADDRESS]
            name = feature["name"]
            _LOGGER.log(LOG_VERBOSE, "Parsing %s: %s (%s)", PLATFORM, name, address)

            if family := feature.get("family"):
                if (
                    isinstance(family, dict)
                    and family[TAG_ADDRESS] == NodeFamily.NODESERVER
                ):
                    feature["node_server"] = family.get("instance", "")
                    feature["protocol"] = self.get_protocol_from_family(
                        feature.get("family")
                    )

            entity = Node(self, address, name, NodeDetail(**feature))
            self.add_or_update_entity(address, name, entity)
        except (TypeError, KeyError, ValueError) as exc:
            _LOGGER.exception("Error loading %s: %s", PLATFORM, exc)

    def parse_group_entity(self, feature: dict[str, Any]) -> None:
        """Parse a single group and add to the platform."""
        try:
            address = feature[TAG_ADDRESS]
            name = feature["name"]
            _LOGGER.log(LOG_VERBOSE, "Parsing %s: %s (%s)", PLATFORM, name, address)
            if (flag := feature["flag"]) & NODE_IS_ROOT:
                _LOGGER.debug("Skipping root group flag=%s %s", flag, address)
                return
            entity = Group(self, address, name, GroupDetail(**feature))
            self.add_or_update_entity(address, name, entity)
        except (TypeError, KeyError, ValueError) as exc:
            _LOGGER.exception("Error loading %s: %s", PLATFORM, exc)

    def get_protocol_from_family(self, family: str | dict[str, str] | None) -> str:
        """Identify protocol from family type."""
        if family is None:
            return Protocol.INSTEON
        if isinstance(family, dict) and family[TAG_ADDRESS] == NodeFamily.NODESERVER:
            node_server = family.get("instance", "")
            self.node_servers.add(node_server)
            return Protocol.NODE_SERVER
        if family in (NodeFamily.ZWAVE, NodeFamily.ZMATTER_ZWAVE):
            return Protocol.ZWAVE
        if family in (NodeFamily.BRULTECH, NodeFamily.RCS):
            return Protocol.ZIGBEE
        return Protocol.INSTEON

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

        if not xml_dict:
            return

        # Write nodes to file for debugging:
        if self.isy.args is not None and self.isy.args.file:
            await self.isy.loop.run_in_executor(
                None,
                write_to_file,
                xml_dict,
                f"{DEFAULT_DIR}rest-status.json",
            )

        while not self.loaded:  # Loaded is set by self.update finishing
            await asyncio.sleep(0.05)
        self.parse_status(xml_dict)

    def parse_status(self, xml_dict: dict[str, Any]) -> None:
        """Parse the results from the ISY."""
        if not (node_statuses := xml_dict["nodes"][TAG_NODE]):
            return

        for status in node_statuses:
            self.parse_node_status(status)

        self.initialized = True

    def parse_node_status(self, status: dict[str, Any]) -> None:
        """Parse the node status results from the ISY."""
        if (address := status["id"]) not in self.addresses:
            return  # FUTURE: Missing address, go get.
        try:
            if not (props := status.get("prop", {})):
                return
            if isinstance(props, dict):
                props = [props]
            entity: Node = cast(Node, self.entities[address])
            for prop in props:
                self.parse_node_properties(prop, entity)

        except (TypeError, KeyError, ValueError) as exc:
            _LOGGER.exception("Error loading node status (%s): %s", address, exc)

    def parse_node_properties(self, prop: dict[str, Any], entity: Node) -> None:
        """Parse the node node property from the ISY."""
        result = NodeProperty(**prop)
        if result.control == PROP_STATUS:
            entity.update_state(result)
            return
        if result.control == PROP_BATTERY_LEVEL and not entity.state_set:
            # Use BATLVL as state if no ST given.
            entity.is_battery_node = True
            entity.update_state(result)
        elif result.control == PROP_RAMP_RATE and result.value:
            result.value = INSTEON_RAMP_RATES.get(str(result.value), result.value)
            result.uom = UOM_SECONDS

        elif result.control not in EVENT_PROPS_IGNORED:
            prop = {result.control: result}
            if prop.items() <= entity.aux_properties.items():
                return  # Property hasn't changed
            entity.aux_properties[result.control] = result

        entity.control_events.notify(result)
        _LOGGER.debug(
            "Received node control for %s: %s",
            entity.name,
            asdict(result),
        )

    async def update_node(self, address: str, wait_time: float = 0) -> None:
        """Update a single node."""
        await asyncio.sleep(wait_time)
        node_url = f"{self.url.rstrip('/')}/{address}?members=true"
        xml_dict = parse_xml(
            await self.isy.conn.request(node_url),
            attr_prefix=self._parse_attr_prefix,
            cdata_key=self._parse_cdata_key,
            use_pp=self._parse_use_pp,
        )
        _LOGGER.log(
            LOG_VERBOSE,
            "%s:\n%s",
            node_url,
            json.dumps(xml_dict, indent=4, sort_keys=True, default=str),
        )

        if not (feature := xml_dict["node_info"]):
            return

        if TAG_FOLDER in feature:
            self.parse_folder_entity(feature[TAG_FOLDER])
        if TAG_NODE in feature:
            self.parse_node_entity(feature[TAG_NODE])
        if TAG_GROUP in feature:
            self.parse_group_entity(feature[TAG_GROUP])
        if TAG_PROPERTIES in feature:
            if not (props := feature[TAG_PROPERTIES].get("prop", {})):
                return
            if not (entity := cast(Node, self.entities.get(address))):
                return
            for prop in props:
                self.parse_node_properties(prop, entity)

    def get_folder(self, address: str) -> str | None:
        """Return the folder of a given node address."""
        if not (entity := self.entities.get(address)):
            raise KeyError(f"Unknown entity address {address}")
        detail = cast(NodeFolderDetail, entity.detail)
        if not detail.parent:
            # Node is in the root folder.
            return None
        parent = detail.parent[TAG_ADDRESS]
        if int(detail.parent["type_"]) != UDHierarchyNodeType.FOLDER:
            return self.get_folder(parent)
        return self.entities[parent].name

    def get_groups(self, address: str, is_controller: bool = True) -> list[str]:
        """
        Return the groups (scenes) of which this node is a member.

        If is_controller is True, only return groups for which this is
        a controller.
        """
        if is_controller:
            return [
                entity.address
                for entity in self.values()
                if isinstance(entity, Group) and address in entity.controllers
            ]
        return [
            entity.address
            for entity in self.values()
            if isinstance(entity, Group) and address in entity.members
        ]

    def get_children(self, address: str) -> set[NodesT]:
        """Return the children of the a given address."""
        return {
            entity
            for entity in self.values()
            if entity.detail.parent and entity.detail.parent[TAG_ADDRESS] == address
        }
