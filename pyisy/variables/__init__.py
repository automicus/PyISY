"""ISY Variables."""
from __future__ import annotations

import asyncio
import copy
from pprint import pformat
from typing import TYPE_CHECKING, Any

from pyisy.constants import (
    METHOD_GET,
    URL_DEFINITIONS,
    URL_VARIABLES,
    VAR_INTEGER,
    VAR_STATE,
)
from pyisy.helpers.entity_platform import EntityPlatform
from pyisy.helpers.xml import parse_xml
from pyisy.logging import _LOGGER, LOG_VERBOSE
from pyisy.variables.variable import Variable

if TYPE_CHECKING:
    from pyisy.isy import ISY

PLATFORM = "variables"

EMPTY_VARIABLES_RESPONSE = [
    "/CONF/INTEGER.VAR not found",
    "/CONF/STATE.VAR not found",
    '<CList type="VAR_INT"></CList>',
]
ATTR_ID = "@id"


class Variables(EntityPlatform):
    """This class handles the ISY variables."""

    def __init__(self, isy: ISY) -> None:
        """Initialize a Variables ISY Variable Manager class.

        Iterate over self.values()
        """
        super().__init__(isy=isy, platform_name=PLATFORM)
        self.isy = isy
        self.url = ""  # Special handling for this platform

    async def update(self, wait_time: float = 0) -> None:
        """Update the contents of the class.

        Variables require 4 calls, so this overloads the base function.
        """
        await asyncio.sleep(wait_time)
        request = self.isy.conn.request
        compile_url = self.isy.conn.compile_url

        endpoints = [
            [URL_VARIABLES, URL_DEFINITIONS, VAR_INTEGER],
            [URL_VARIABLES, URL_DEFINITIONS, VAR_STATE],
            [URL_VARIABLES, METHOD_GET, VAR_INTEGER],
            [URL_VARIABLES, METHOD_GET, VAR_STATE],
        ]
        urls = [compile_url(e) for e in endpoints]

        results = await asyncio.gather(
            *[request(url) for url in urls], return_exceptions=True
        )

        # Check if Integer Variables defined
        if not (results[0] is None or results[0] in EMPTY_VARIABLES_RESPONSE):
            xml_int_def = parse_xml(results[0])
            xml_int = parse_xml(results[2])
            int_dict = {
                PLATFORM: [
                    v | xml_int["vars"]["var"][i]
                    for i, v in enumerate(xml_int_def["CList"]["e"])
                ]
            }
            _LOGGER.log(
                LOG_VERBOSE,
                "%s:\n%s",
                urls[2],
                pformat(int_dict),
            )
            await self.parse(int_dict)

        # Check if State Variables defined
        if not (results[1] is None or results[1] in EMPTY_VARIABLES_RESPONSE):
            xml_state_def = parse_xml(results[1])
            xml_state = parse_xml(results[3])
            state_dict = {
                PLATFORM: [
                    v | xml_state["vars"]["var"][i]
                    for i, v in enumerate(xml_state_def["CList"]["e"])
                ]
            }
            _LOGGER.log(
                LOG_VERBOSE,
                "%s:\n%s",
                urls[3],
                pformat(state_dict),
            )
            await self.parse(state_dict)

    async def parse(self, xml_dict: dict[str, Any]):
        """Parse XML from the controller with details about the variables.

        Expected format for detailed information:
        detail = {
            "@id": "1",
            "@name": "variable name",
            "@type": "2",
            "init": "0",
            "prec": "0",
            "ts": "20230102 14:02:07",
            "val": "0",
        }
        """
        for feature in xml_dict[PLATFORM]:
            address = f"{feature['@type']}.{feature['@id']}"
            name = feature["@name"]
            detail = copy.deepcopy(feature)
            entity = Variable(self, address, name, detail)
            await self.add_or_update_entity(address, name, entity)

        _LOGGER.info("ISY Loaded Variables")

    # def update_received(self, xmldoc):
    #     """Process an update received from the event stream."""
    #     xml = xmldoc.toxml()
    #     vtype = int(attr_from_xml(xmldoc, ATTR_VAR, TAG_TYPE))
    #     vid = int(attr_from_xml(xmldoc, ATTR_VAR, ATTR_ID))
    #     try:
    #         vobj = self.vobjs[vtype][vid]
    #     except KeyError:
    #         return  # this is a new variable that hasn't been loaded

    #     vobj.last_update = now()
    #     if f"<{ATTR_INIT}>" in xml:
    #         vobj.init = int(value_from_xml(xmldoc, ATTR_INIT))
    #     else:
    #         vobj.status = int(value_from_xml(xmldoc, ATTR_VAL))
    #         vobj.prec = int(value_from_xml(xmldoc, ATTR_PRECISION, 0))
    #         vobj.last_edited = parser.parse(value_from_xml(xmldoc, ATTR_TS))

    #     _LOGGER.debug("ISY Updated Variable: %s.%s", str(vtype), str(vid))

    # def __getitem__(self, val):
    #     """
    #     Navigate through the variables by ID or name.

    #     |  val: Name or ID for navigation.
    #     """
    #     if self.root is None:
    #         if val in [1, 2]:
    #             return Variables(self.isy, val, self.vids, self.vnames, self.vobjs)
    #         raise KeyError(f"Unknown variable type: {val}")
    #     if isinstance(val, int):
    #         try:
    #             return self.vobjs[self.root][val]
    #         except (ValueError, KeyError) as err:
    #             raise KeyError(f"Unrecognized variable id: {val}") from err

    #     for vid, vname in self.vnames[self.root]:
    #         if vname == val:
    #             return self.vobjs[self.root][vid]
    #     raise KeyError(f"Unrecognized variable name: {val}")

    # def __setitem__(self, val, value):
    #     """Handle the setitem function for the Class."""
    #     return None

    # def get_by_name(self, val):
    #     """
    #     Get a variable with the given name.

    #     |  val: The name of the variable to look for.
    #     """
    #     vtype, _, vid = next(item for item in self.children if val in item)
    #     if not vid and vtype:
    #         raise KeyError(f"Unrecognized variable name: {val}")
    #     return self.vobjs[vtype].get(vid)

    # @property
    # def children(self):
    #     """Get the children of the class."""
    #     if self.root is None:
    #         types = [1, 2]
    #     else:
    #         types = [self.root]

    #     out = []
    #     for vtype in types:
    #         for ind in range(len(self.vids[vtype])):
    #             out.append(
    #                 (
    #                     vtype,
    #                     self.vnames[vtype].get(self.vids[vtype][ind], ""),
    #                     self.vids[vtype][ind],
    #                 )
    #             )
    #     return out
