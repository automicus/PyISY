"""ISY Node Server Information."""
import asyncio
from dataclasses import dataclass
import re
from typing import Dict, List
from xml.dom import getDOMImplementation, minidom

from .constants import (
    ATTR_ID,
    ATTR_UNIT_OF_MEASURE,
    TAG_ENABLED,
    TAG_NAME,
    TAG_ROOT,
    URL_PROFILE_NS,
)
from .exceptions import XML_ERRORS, XML_PARSE_ERROR, ISYResponseParseError
from .helpers import attr_from_element, value_from_xml
from .logging import _LOGGER

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
TAG_NODE_DEF = "nodeDef"
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

    def __init__(self, isy, slots: list[str]):
        """
        Initialize the NodeServers class.

        isy: ISY class
        slots: List of slot numbers
        """
        self.isy = isy
        self._slots = slots
        self._connections = []
        self._profiles = {}
        self._node_server_node_definitions = []
        self._node_server_node_editors = []
        self._node_server_nls = []
        self.loaded = False

    async def load_node_servers(self):
        """Load information about node servers from the ISY."""

        await self.get_connection_info()
        await self.get_node_server_profiles()
        for slot in self._slots:
            await self.parse_node_server_defs(slot)
        self.loaded = True
        _LOGGER.info("ISY updated node servers")
        # _LOGGER.debug(self._node_server_node_definitions)
        # _LOGGER.debug(self._node_server_node_editors)

    async def get_connection_info(self):
        """Fetch the node server connections from the ISY."""
        result = await self.isy.conn.request(
            self.isy.conn.compile_url([URL_PROFILE_NS, "0", "connection"]),
            ok404=False,
        )
        if result is None:
            return

        try:
            connections_xml = minidom.parseString(result)
        except XML_ERRORS as exc:
            _LOGGER.error("%s while parsing Node Server connections", XML_PARSE_ERROR)
            raise ISYResponseParseError(XML_PARSE_ERROR) from exc

        connections = connections_xml.getElementsByTagName(TAG_CONNECTION)
        for connection in connections:
            self._connections.append(
                NodeServerConnection(
                    slot=attr_from_element(connection, ATTR_PROFILE),
                    enabled=attr_from_element(connection, TAG_ENABLED),
                    name=value_from_xml(connection, TAG_NAME),
                    ssl=value_from_xml(connection, TAG_SSL),
                    sni=value_from_xml(connection, TAG_SNI),
                    port=value_from_xml(connection, TAG_PORT),
                    timeout=value_from_xml(connection, TAG_TIMEOUT),
                    isy_user_num=value_from_xml(connection, TAG_ISY_USER_NUM),
                    ip=value_from_xml(connection, TAG_IP),
                    base_url=value_from_xml(connection, TAG_BASE_URL),
                    ns_user=value_from_xml(connection, TAG_NS_USER),
                )
            )
        _LOGGER.info("ISY updated node server connection info")

    async def get_node_server_profiles(self):
        """Retrieve the node server definition files from the ISY."""
        node_server_file_list = await self.isy.conn.request(
            self.isy.conn.compile_url([URL_PROFILE_NS, "0", "files"]), ok404=False
        )

        if node_server_file_list is None:
            return

        _LOGGER.debug("Parsing node server file list")

        try:
            file_list_xml = minidom.parseString(node_server_file_list)
        except XML_ERRORS as exc:
            _LOGGER.error("%s while parsing Node Server files", XML_PARSE_ERROR)
            raise ISYResponseParseError(XML_PARSE_ERROR) from exc

        file_list: List[str] = []

        profiles = file_list_xml.getElementsByTagName(ATTR_PROFILE)
        for profile in profiles:
            slot = attr_from_element(profile, ATTR_ID)
            directories = profile.getElementsByTagName(TAG_FILES)
            for directory in directories:
                dir_name = attr_from_element(directory, ATTR_DIR)
                files = directory.getElementsByTagName(TAG_FILE)
                for file in files:
                    file_name = attr_from_element(file, TAG_NAME)
                    file_list.append(f"{slot}/download/{dir_name}/{file_name}")

        file_tasks = [
            self.isy.conn.request(self.isy.conn.compile_url([URL_PROFILE_NS, file]))
            for file in file_list
        ]
        file_contents: List[str] = await asyncio.gather(*file_tasks)
        self._profiles: dict = dict(zip(file_list, file_contents))

        _LOGGER.info("ISY downloaded node server files")

    async def parse_node_server_defs(self, slot: str):
        """Retrieve and parse the node server definitions."""
        _LOGGER.info("Parsing node server slot %s", slot)
        node_server_profile = {
            key: value
            for (key, value) in self._profiles.items()
            if key.startswith(slot)
        }

        node_defs_impl = getDOMImplementation()
        editors_impl = getDOMImplementation()
        node_defs_xml = node_defs_impl.createDocument(None, TAG_ROOT, None)
        editors_xml = editors_impl.createDocument(None, TAG_ROOT, None)
        nls_lookup: dict = {}

        for file, contents in node_server_profile.items():
            contents_xml = ""
            file = file.lower()
            if file.endswith(".xml"):
                try:
                    contents_xml = minidom.parseString(contents).firstChild
                except XML_ERRORS:
                    _LOGGER.error(
                        "%s while parsing Node Server %s file %s",
                        XML_PARSE_ERROR,
                        slot,
                        file,
                    )
                    continue
            if "nodedef" in file:
                node_defs_xml.firstChild.appendChild(contents_xml)
            if "editors" in file:
                editors_xml.firstChild.appendChild(contents_xml)
            if "nls" in file and "en_us" in file:
                nls_list = [
                    line
                    for line in contents.split("\n")
                    if not line.startswith("#") and line != ""
                ]
                if nls_list:
                    nls_lookup = dict(re.split(r"\s?=\s?", line) for line in nls_list)
                    self._node_server_nls.append(
                        NodeServerNLS(
                            slot=slot,
                            nls=nls_lookup,
                        )
                    )

        # Process Node Def Files
        node_defs = node_defs_xml.getElementsByTagName(TAG_NODE_DEF)
        for node_def in node_defs:
            node_def_id = attr_from_element(node_def, ATTR_ID)
            nls_prefix = attr_from_element(node_def, ATTR_NLS)
            sts = node_def.getElementsByTagName(TAG_ST)
            statuses = {}
            for st in sts:
                status_id = attr_from_element(st, ATTR_ID)
                editor = attr_from_element(st, ATTR_EDITOR)
                statuses.update({status_id: editor})

            cmds_sends = node_def.getElementsByTagName(TAG_SENDS)[0]
            cmds_accepts = node_def.getElementsByTagName(TAG_ACCEPTS)[0]
            cmds_sends_cmd = cmds_sends.getElementsByTagName(TAG_CMD)
            cmds_accepts_cmd = cmds_accepts.getElementsByTagName(TAG_CMD)
            sends_commands = []
            accepts_commands = []

            for cmd in cmds_sends_cmd:
                sends_commands.append(attr_from_element(cmd, ATTR_ID))
            for cmd in cmds_accepts_cmd:
                accepts_commands.append(attr_from_element(cmd, ATTR_ID))

            status_names = {}
            name = node_def_id
            if nls_lookup:
                if (name_key := f"ND-{node_def_id}-NAME") in nls_lookup:
                    name = nls_lookup[name_key]
                for st in statuses:
                    if (key := f"ST-{nls_prefix}-{st}-NAME") in nls_lookup:
                        status_names.update({st: nls_lookup[key]})

            self._node_server_node_definitions.append(
                NodeServerNodeDefinition(
                    node_def_id=node_def_id,
                    name=name,
                    nls_prefix=nls_prefix,
                    slot=slot,
                    statuses=statuses,
                    status_names=status_names,
                    sends_commands=sends_commands,
                    accepts_commands=accepts_commands,
                )
            )
        # Process Editor Files
        editors = editors_xml.getElementsByTagName(ATTR_EDITOR)
        for editor in editors:
            editor_id = attr_from_element(editor, ATTR_ID)
            editor_range = editor.getElementsByTagName(TAG_RANGE)[0]
            uom = attr_from_element(editor_range, ATTR_UNIT_OF_MEASURE)
            subset = attr_from_element(editor_range, ATTR_SUBSET)
            nls = attr_from_element(editor_range, ATTR_NLS)

            values = None
            if nls_lookup and uom == "25":
                values = {
                    key.partition("-")[2]: value
                    for (key, value) in nls_lookup.items()
                    if key.startswith(nls)
                }

            self._node_server_node_editors.append(
                NodeServerNodeEditor(
                    editor_id=editor_id,
                    unit_of_measurement=uom,
                    subset=subset,
                    nls=nls,
                    slot=slot,
                    values=values,
                )
            )

        _LOGGER.debug("ISY parsed node server profiles")


@dataclass
class NodeServerNodeDefinition:
    """Node Server Node Definition parsed from the ISY/IoX."""

    node_def_id: str
    name: str
    nls_prefix: str
    slot: str
    statuses: Dict[str, str]
    status_names: Dict[str, str]
    sends_commands: List[str]
    accepts_commands: List[str]


@dataclass
class NodeServerNodeEditor:
    """Node Server Editor definition."""

    editor_id: str
    unit_of_measurement: str
    subset: str
    nls: str
    slot: str
    values: Dict[str, str]


@dataclass
class NodeServerNLS:
    """Node Server Natural Language Selection definition."""

    slot: str
    nls: Dict[str, str]


@dataclass
class NodeServerConnection:
    """Node Server Connection details."""

    slot: str
    enabled: str
    name: str
    ssl: str
    sni: str
    port: str
    timeout: str
    isy_user_num: str
    ip: str
    base_url: str
    ns_user: str

    def configuration_url(self) -> str:
        """Compile a configuration url from the connection data."""
        protocol: str = "https://" if self.ssl else "http://"
        return f"{protocol}{self.ip}:{self.port}"
