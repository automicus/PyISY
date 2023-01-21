"""ISY Node Server Information."""
from __future__ import annotations

import asyncio
from dataclasses import InitVar, asdict, dataclass, field
import json
import re
from typing import TYPE_CHECKING, Any

from pyisy.constants import ATTR_ID, TAG_NAME, UOM_INDEX, URL_PROFILE_NS
from pyisy.helpers.xml import parse_xml
from pyisy.logging import _LOGGER
from pyisy.util.output import write_to_file

if TYPE_CHECKING:
    from pyisy.isy import ISY


ATTR_DIR = "dir"
ATTR_EDITOR = "editor"
ATTR_NLS = "nls"
ATTR_SUBSET = "subset"
ATTR_PROFILE = "profile"

TAG_ACCEPTS = "accepts"
TAG_CMD = "cmd"
TAG_CONNECTION = "connection"
TAG_FILE = "file"
TAG_FILES = "files"
TAG_IP = "ip"
TAG_BASE_URL = "baseurl"
TAG_ISY_USER_NUM = "isyusernum"
TAG_NODE_DEF = "node_def"
TAG_NS_USER = "nsuser"
TAG_PORT = "port"
TAG_RANGE = "range"
TAG_SENDS = "sends"
TAG_SNI = "sni"
TAG_SSL = "ssl"
TAG_ST = "st"
TAG_TIMEOUT = "timeout"


class NodeServers:
    """
    ISY NodeServers class object.

    DESCRIPTION:
        This class handles the ISY Node Servers info.

    ATTRIBUTES:
        isy: The ISY device class

    """

    isy: ISY
    _connections: list = []
    slots: set = set()
    _node_server_node_definitions: dict[str, dict[str, NodeServerNodeDefinition]] = {}
    _node_server_node_editors: dict[str, dict[str, NodeServerNodeEditor]] = {}
    _node_server_nls: dict = {}
    loaded: bool = False
    bg_tasks: set = set()

    def __init__(self, isy: ISY):
        """Initialize the NodeServers class."""
        self.isy = isy

    async def update(self) -> None:
        """Load information about node servers from the ISY."""
        ns_conn_task = asyncio.create_task(self.get_connection_info())
        self.bg_tasks.add(ns_conn_task)
        ns_conn_task.add_done_callback(self.bg_tasks.discard)

        ns_profile_task = asyncio.create_task(self.get_node_server_profiles())
        self.bg_tasks.add(ns_profile_task)
        ns_profile_task.add_done_callback(self.bg_tasks.discard)

        while self.bg_tasks:
            await asyncio.sleep(0.05)

        for slot in self.slots:
            await self.parse_nls_info_for_slot(slot)
        self.loaded = True
        _LOGGER.info("Updated node servers")

    async def get_connection_info(self) -> None:
        """Fetch the node server connections from the ISY."""
        result = await self.isy.conn.request(
            self.isy.conn.compile_url([URL_PROFILE_NS, "0", "connection"]),
            ok404=False,
        )
        if result is None:
            return

        ns_conn_xml = parse_xml(result)

        if self.isy.args and self.isy.args.file:
            await write_to_file(ns_conn_xml, ".output/node-server-connections.json")

        if not (connections := ns_conn_xml["connections"]):
            return

        if isinstance((connection_list := connections["connection"]), dict):
            connection_list = [connection_list]  # Handle case for 1 Node Server

        for connection in connection_list:
            await self.parse_connection(connection)

        _LOGGER.debug("Updated node server connection info")

    async def parse_connection(self, conn: dict) -> None:
        """Parse the node server connection files from the ISY."""
        try:
            self._connections.append(NodeServerConnection(**conn))
        except (ValueError, KeyError, NameError) as exc:
            _LOGGER.error("Could not parse node server connection: %s", exc)
            return

    async def get_node_server_profiles(self) -> None:
        """Retrieve the node server definition files from the ISY."""
        result = await self.isy.conn.request(
            self.isy.conn.compile_url([URL_PROFILE_NS, "0", TAG_FILES]), ok404=False
        )

        if result is None:
            return

        ns_conn_xml = parse_xml(result)

        if self.isy.args and self.isy.args.file:
            await write_to_file(ns_conn_xml, ".output/node-server-profiles.json")

        if not (profiles := ns_conn_xml["profiles"]):
            return

        if isinstance((profile_list := profiles["profile"]), dict):
            profile_list = [profile_list]  # Handle case for 1 Node Server

        for profile in profile_list:
            await self.parse_profile(profile)

        _LOGGER.debug("Downloaded node server files")

    async def parse_profile(self, profile: dict) -> None:
        """Parse the node server profile file list from the ISY."""
        try:
            slot = profile["id"]
            files: list[dict] = profile[TAG_FILES]

            for file in files:
                dir_name = file["dir"]
                file_name = file[TAG_FILE][TAG_NAME]
                file_path = f"{slot}/download/{dir_name}/{file_name}"

                task = asyncio.create_task(self.fetch_node_server_file(file_path))
                self.bg_tasks.add(task)
                task.add_done_callback(self.bg_tasks.discard)

            self.slots.add(slot)

        except (ValueError, KeyError, NameError) as exc:
            _LOGGER.error("Could not parse node server profile: %s", exc)
            return

    async def fetch_node_server_file(self, path: str) -> None:
        """Fetch a node server file from the ISY."""
        result = await self.isy.conn.request(
            self.isy.conn.compile_url([URL_PROFILE_NS, path])
        )
        if result is None:
            return
        await self.parse_node_server_file(path, result)

    async def parse_node_server_file(self, path: str, file_content: str) -> None:
        """Retrieve and parse the node server definitions."""
        slot = path.split("/")[0]
        path = path.lower()

        _LOGGER.debug(
            "Parsing node server %s file %s", slot, "/".join(path.split("/")[-2:])
        )
        if path.endswith(".xml"):
            xml_dict = parse_xml(file_content)

            if self.isy.args and self.isy.args.file:
                filename = "-".join(path.split("/")[-2:]).replace(".xml", ".json")
                await write_to_file(
                    xml_dict,
                    f".output/ns-{slot}-{filename}",
                )

            if "nodedef" in path:
                if node_defs := xml_dict["node_defs"]:
                    if isinstance((nd_list := node_defs[TAG_NODE_DEF]), dict):
                        nd_list = [nd_list]
                    self._node_server_node_definitions[slot] = {}
                    for node_def in nd_list:
                        await self.parse_node_server_defs(slot, node_def)
                return
            if "editor" in path:
                if editors := xml_dict["editors"]:
                    if isinstance((editor_list := editors["editor"]), dict):
                        editor_list = [editor_list]
                    self._node_server_node_editors[slot] = {}
                    for editor in editor_list:
                        await self.parse_node_server_editor(slot, editor)
                return
        elif "nls/en_us" in path:
            nls_lookup: dict = {}
            nls_list = [
                line
                for line in file_content.split("\n")
                if not line.startswith("#") and line != ""
            ]
            if nls_list:
                nls_lookup = dict(re.split(r"\s?=\s?", line) for line in nls_list)
                self._node_server_nls[slot] = nls_lookup

            if self.isy.args and self.isy.args.file:
                filename = "-".join(path.split("/")[-2:]).replace(".txt", ".json")
                await write_to_file(
                    nls_lookup,
                    f".output/ns-{slot}-{filename}",
                )

            return
        _LOGGER.warning(
            "Unknown file for slot %s: %s", slot, "/".join(path.split("/")[-2:])
        )

    async def parse_node_server_defs(self, slot: str, node_def: dict) -> None:
        """Retrieve and parse the node server definitions."""
        try:
            self._node_server_node_definitions[slot][
                node_def["id"]
            ] = NodeServerNodeDefinition(**node_def)

        except (ValueError, KeyError, NameError) as exc:
            _LOGGER.error("Could not parse node server connection: %s", exc)
            return

    async def parse_node_server_editor(self, slot: str, editor: dict) -> None:
        """Retrieve and parse the node server definitions."""
        editor_id = editor[ATTR_ID]
        editor_range = NodeServerEditorRange(**editor[TAG_RANGE])

        self._node_server_node_editors[slot][editor_id] = NodeServerNodeEditor(
            editor_id=editor_id,
            range=editor_range,
            slot=slot,
        )

    async def parse_nls_info_for_slot(self, slot: str) -> None:
        """Fetch the node server connections from the ISY."""
        try:
            # Update NLS information
            if slot not in self._node_server_nls:
                # Missing NLS file for this node server
                return
            nls = self._node_server_nls[slot]
            if not (editors := self._node_server_node_editors.get(slot)):
                return

            for editor in editors.values():
                if editor.range.uom == UOM_INDEX and editor.range.nls:
                    editor.values = {
                        k.replace(f"{editor.range.nls}-", ""): v
                        for k, v in nls.items()
                        if k.startswith(editor.range.nls)
                    }

            if not (node_defs := self._node_server_node_definitions.get(slot)):
                return
            for node_def in node_defs.values():
                if (name_key := f"ND-{node_def.id}-NAME") in nls:
                    node_def.name = nls[name_key]

                for st_id, st_editor in node_def.statuses.items():
                    if (key := f"ST-{node_def.nls}-{st_id}-NAME") in nls:
                        node_def.status_names[st_id] = nls[key]
                    node_def.status_editors[st_id] = editors[st_editor]
        except (ValueError, KeyError, NameError) as exc:
            _LOGGER.error(
                "Error parsing language information for node server slot %s: %s",
                slot,
                exc,
            )

    async def to_dict(self) -> dict:
        """Dump entity platform entities to dict."""
        return {
            "connections": [conn.__dict__ for conn in self._connections],
            "node_defs": {
                slot: {k: asdict(v) for k, v in node_def.items()}
                for slot, node_def in self._node_server_node_definitions.items()
            },
        }

    def __str__(self) -> str:
        """Return a string representation of the node servers."""
        return f"<{type(self).__name__} slots={self.slots} loaded={self.loaded}>"

    def __repr__(self) -> str:
        """Return a string representation of the node servers."""
        return (
            f"<{type(self).__name__} slots={self.slots} loaded={self.loaded}>"
            f" detail:\n{json.dumps(self._node_server_node_definitions, sort_keys=True, default=str)}"
        )


@dataclass
class NodeServerEditorRange:
    """Node Server Editor Range definition."""

    uom: str = ""
    min: str = ""
    max: str = ""
    precision: int = 0
    subset: str = ""
    nls: str = ""


@dataclass
class NodeServerNodeEditor:
    """Node Server Editor definition."""

    editor_id: str = ""
    range: NodeServerEditorRange = NodeServerEditorRange()
    nls: str = ""
    slot: str = ""
    values: dict[str, str] = field(default_factory=dict)


@dataclass
class NodeServerConnection:
    """Node Server Connection details."""

    profile: str = ""
    type_: str = ""
    enabled: bool = False
    name: str = ""
    ssl: bool = False
    sni: bool = False
    port: str = ""
    timeout: str = ""
    isyusernum: str = ""
    ip: str = ""
    baseurl: str = ""
    nsuser: str = ""

    def configuration_url(self) -> str:
        """Compile a configuration url from the connection data."""
        protocol: str = "https://" if self.ssl else "http://"
        return f"{protocol}{self.ip}:{self.port}"


@dataclass
class NodeServerNodeDefinition:
    """Node Server Node Definition parsed from the ISY/IoX."""

    sts: InitVar[dict[str, list | dict]]
    cmds: InitVar[dict[str, Any]]
    id: str = ""
    node_type: str = ""
    name: str = ""
    nls: str = ""
    slot: str = ""
    editors: Any = ""
    statuses: dict[str, str] = field(init=False, default_factory=dict)
    status_names: dict[str, str] = field(default_factory=dict)
    status_editors: dict[str, NodeServerNodeEditor] = field(default_factory=dict)
    sends: dict[str, Any] = field(init=False, default_factory=dict)
    accepts: dict[str, Any] = field(init=False, default_factory=dict)

    def __post_init__(self, sts: dict[str, list | dict], cmds: dict[str, Any]) -> None:
        """Post-process node server definition."""
        statuses = {}
        if sts:
            if isinstance(st_list := sts["st"], dict):
                st_list = [st_list]
            for st in st_list:
                statuses.update({st["id"]: st["editor"]})
        self.statuses = statuses

        if cmds_sends := cmds["sends"]:
            if isinstance((cmd_list := cmds_sends["cmd"]), dict):
                cmd_list = [cmd_list]
            self.sends = {i["id"]: i for i in cmd_list}

        if cmds_accepts := cmds["accepts"]:
            if isinstance((cmd_list := cmds_accepts["cmd"]), dict):
                cmd_list = [cmd_list]
            self.accepts = {i["id"]: i for i in cmd_list}
