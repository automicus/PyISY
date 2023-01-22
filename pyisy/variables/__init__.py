"""ISY Variables."""
from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any, cast

from pyisy.constants import (
    URL_DEFINITIONS,
    URL_GET,
    URL_VARIABLES,
    VAR_INTEGER,
    VAR_STATE,
)
from pyisy.events.router import EventData
from pyisy.helpers import convert_isy_raw_value
from pyisy.helpers.entity_platform import EntityPlatform
from pyisy.helpers.xml import parse_xml
from pyisy.logging import _LOGGER, LOG_VERBOSE
from pyisy.util.output import write_to_file
from pyisy.variables.variable import Variable, VariableDetail

if TYPE_CHECKING:
    from pyisy.isy import ISY

PLATFORM = "variables"

EMPTY_VARIABLES_RESPONSE = [
    "/CONF/INTEGER.VAR not found",
    "/CONF/STATE.VAR not found",
    '<CList type="VAR_INT"></CList>',
]


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
            [URL_VARIABLES, URL_GET, VAR_INTEGER],
            [URL_VARIABLES, URL_GET, VAR_STATE],
        ]
        urls = [compile_url(e) for e in endpoints]

        results = await asyncio.gather(
            *[request(url) for url in urls], return_exceptions=True
        )

        # Check if Integer Variables defined
        if not (results[0] is None or results[0] in EMPTY_VARIABLES_RESPONSE):
            xml_int_def = parse_xml(results[0], attr_prefix="")
            xml_int = parse_xml(results[2], attr_prefix="")
            int_dict = {
                PLATFORM: [
                    v | xml_int["vars"]["var"][i]
                    for i, v in enumerate(xml_int_def["c_list"]["e"])
                ]
            }

            if self.isy.args is not None and self.isy.args.file:
                await write_to_file(int_dict, ".output/rest-variables-integer.json")
            _LOGGER.log(
                LOG_VERBOSE,
                "%s:\n%s",
                urls[2],
                json.dumps(int_dict, indent=4, sort_keys=True, default=str),
            )
            await self.parse(int_dict)
            self.loaded = True

        # Check if State Variables defined
        if not (results[1] is None or results[1] in EMPTY_VARIABLES_RESPONSE):
            xml_state_def = parse_xml(results[1], attr_prefix="")
            xml_state = parse_xml(results[3], attr_prefix="")
            state_dict = {
                PLATFORM: [
                    v | xml_state["vars"]["var"][i]
                    for i, v in enumerate(xml_state_def["c_list"]["e"])
                ]
            }

            if self.isy.args is not None and self.isy.args.file:
                await write_to_file(int_dict, ".output/rest-variables-state.json")
            _LOGGER.log(
                LOG_VERBOSE,
                "%s:\n%s",
                urls[3],
                json.dumps(state_dict, indent=4, sort_keys=True, default=str),
            )
            await self.parse(state_dict)
            self.loaded = True

    async def parse(self, xml_dict: dict[str, Any]) -> None:
        """Parse XML from the controller with details about the variables."""
        if not (features := xml_dict[PLATFORM]):
            return
        for feature in features:
            await self.parse_entity(feature)
        _LOGGER.info(
            "Loaded %s %s",
            "state" if features[0]["type_"] == "2" else "integer",
            PLATFORM,
        )

    async def parse_entity(self, feature: dict[str, Any]) -> None:
        """Parse a single value and add it to the platform."""
        try:
            address = f"{feature['type_']}.{feature['id']}"
            name = feature["name"]
            _LOGGER.log(LOG_VERBOSE, "Parsing %s: %s (%s)", PLATFORM, name, address)
            detail = VariableDetail(**feature)
            entity = Variable(self, address, name, detail)
            await self.add_or_update_entity(address, name, entity)
        except (TypeError, KeyError, ValueError) as exc:
            _LOGGER.exception("Error loading %s: %s", PLATFORM, exc)

    async def update_received(self, event: EventData, init: bool = False) -> None:
        """Process an update received from the event stream."""
        event_info: dict[str, dict] = cast(dict, event.event_info)
        var_info = event_info["var"]

        if (address := f"{var_info['type_']}.{var_info['id']}") not in self.addresses:
            # New/unknown variable, refresh full set.
            await self.update()
            return
        entity = self.entities[address]
        detail = cast(VariableDetail, entity.detail)

        detail.precision = var_info["precision"]
        if init:
            detail.initial = convert_isy_raw_value(
                int(var_info["init"]), "", var_info["precision"]
            )
        else:
            detail.value = convert_isy_raw_value(
                int(var_info["val"]), "", var_info["precision"]
            )
        entity.update_entity(name=entity.name, detail=detail)
        _LOGGER.debug(
            "Updated variable: %s detail=%s",
            address,
            json.dumps(detail.__dict__, default=str),
        )
