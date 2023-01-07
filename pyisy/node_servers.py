"""ISY Node Server Information."""
import asyncio
from dataclasses import dataclass
import re
from typing import Dict, List
from xml.dom import getDOMImplementation, minidom

from .constants import _LOGGER, ATTR_ID, ATTR_UNIT_OF_MEASURE
from .exceptions import XML_ERRORS, XML_PARSE_ERROR, ISYResponseParseError
from .helpers import attr_from_element

ATTR_NODE_DEF = "nodeDef"
ATTR_NLS = "nls"
ATTR_ST = "st"
ATTR_EDITOR = "editor"
ATTR_SENDS = "sends"
ATTR_ACCEPTS = "accepts"
ATTR_CMD = "cmd"
ATTR_RANGE = "range"
ATTR_SUBSET = "subset"


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
        self._node_server_node_definitions = []
        self._node_server_node_editors = []
        self._node_server_nls = []

    async def load_node_servers(self):
        """Load information about node servers from the ISY."""
        for slot in self._slots:
            await self.get_node_server_defs(slot)

    async def get_node_server_defs(self, slot: str):
        """Retrieve and parse the node server definitions."""
        url_base = self.isy.conn.compile_url(["profiles/ns", slot])
        node_server_file_list = await self.isy.conn.request(
            f"{url_base}/files", ok404=False
        )
        _LOGGER.info("Parsing node server slot %s", slot)

        if node_server_file_list is None:
            return

        try:
            file_list_xml = minidom.parseString(node_server_file_list)
        except XML_ERRORS:
            _LOGGER.error(
                "%s while parsing Node Server %s files", XML_PARSE_ERROR, slot
            )
            raise ISYResponseParseError(XML_PARSE_ERROR)

        file_list: List[str] = []
        directories = file_list_xml.getElementsByTagName("files")

        for directory in directories:
            dir_name = attr_from_element(directory, "dir")
            files = directory.getElementsByTagName("file")
            for file in files:
                file_name = attr_from_element(file, "name")
                file_list.append(f"{dir_name}/{file_name}")

        file_tasks = [
            self.isy.conn.request(f"{url_base}/download/{file}") for file in file_list
        ]
        file_contents: List[str] = await asyncio.gather(*file_tasks)
        node_server_profile: dict = dict(zip(file_list, file_contents))
        node_defs_impl = getDOMImplementation()
        editors_impl = getDOMImplementation()
        node_defs_xml = node_defs_impl.createDocument(None, "root", None)
        editors_xml = editors_impl.createDocument(None, "root", None)
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
                    raise ISYResponseParseError(XML_PARSE_ERROR)
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
                nls_lookup = dict(re.split(r"\s?=\s?", line) for line in nls_list)
                self._node_server_nls.append(
                    NodeServerNLS(
                        slot=slot,
                        nls=nls_lookup,
                    )
                )

        # Process Node Def Files
        node_defs = node_defs_xml.getElementsByTagName(ATTR_NODE_DEF)
        for node_def in node_defs:
            node_def_id = attr_from_element(node_def, ATTR_ID)
            nls_prefix = attr_from_element(node_def, ATTR_NLS)
            sts = node_def.getElementsByTagName(ATTR_ST)
            statuses = {}
            for st in sts:
                status_id = attr_from_element(st, ATTR_ID)
                editor = attr_from_element(st, ATTR_EDITOR)
                statuses.update({status_id: editor})

            cmds_sends = node_def.getElementsByTagName(ATTR_SENDS)[0]
            cmds_accepts = node_def.getElementsByTagName(ATTR_ACCEPTS)[0]
            cmds_sends_cmd = cmds_sends.getElementsByTagName(ATTR_CMD)
            cmds_accepts_cmd = cmds_accepts.getElementsByTagName(ATTR_CMD)
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
            editor_range = editor.getElementsByTagName(ATTR_RANGE)[0]
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

        _LOGGER.info("ISY updated node servers.")


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
