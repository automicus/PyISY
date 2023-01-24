"""ISY Variables."""
from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any, cast

from pyisy.constants import (
    ATTR_ID,
    ATTR_TYPE,
    ATTR_VAR,
    DEFAULT_DIR,
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


class Variables(EntityPlatform[Variable]):
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
        await self.check_if_variables_defined("integer", results[0], results[2])
        # Check if State Variables defined
        await self.check_if_variables_defined("state", results[1], results[3])

    async def check_if_variables_defined(
        self, var_type: str, def_result: str, var_result: str
    ) -> None:
        """Check if variables are correctly defined and collect dict."""
        if def_result is None or def_result in EMPTY_VARIABLES_RESPONSE:
            return None

        def_dict = parse_xml(def_result, attr_prefix="")
        if not (def_list := def_dict.get("c_list")) or not (
            e_list := def_list.get("e")
        ):
            return None

        # Handle single variable edge case
        if isinstance(e_list, dict):
            e_list = [e_list]

        var_dict = parse_xml(var_result, attr_prefix="")
        if not (var_list := var_dict["vars"][ATTR_VAR]):
            return None

        if isinstance(var_list, dict):
            var_list = [var_list]

        var_dict = {PLATFORM: [v | var_list[i] for i, v in enumerate(e_list)]}

        if self.isy.args is not None and self.isy.args.file:
            await self.isy.loop.run_in_executor(
                None,
                write_to_file,
                var_dict,
                f"{DEFAULT_DIR}rest-{PLATFORM}-{var_type}.json",
            )

        _LOGGER.log(
            LOG_VERBOSE,
            "%s:\n%s",
            var_type,
            json.dumps(var_dict, indent=4, sort_keys=True, default=str),
        )
        self.parse(var_dict)
        self.loaded = True

    def parse(self, xml_dict: dict[str, Any]) -> None:
        """Parse XML from the controller with details about the variables."""
        if not (features := xml_dict[PLATFORM]):
            return
        for feature in features:
            self.parse_entity(feature)
        _LOGGER.info(
            "Loaded %s %s",
            "state" if features[0][ATTR_TYPE] == "2" else "integer",
            PLATFORM,
        )

    def parse_entity(self, feature: dict[str, Any]) -> None:
        """Parse a single value and add it to the platform."""
        try:
            address = f"{feature[ATTR_TYPE]}.{feature[ATTR_ID]}"
            name = feature["name"]
            _LOGGER.log(LOG_VERBOSE, "Parsing %s: %s (%s)", PLATFORM, name, address)
            detail = VariableDetail(**feature)
            entity = Variable(self, address, name, detail)
            self.add_or_update_entity(address, name, entity)
        except (TypeError, KeyError, ValueError) as exc:
            _LOGGER.exception("Error loading %s: %s", PLATFORM, exc)

    def update_received(self, event: EventData, init: bool = False) -> None:
        """Process an update received from the event stream."""
        event_info: dict[str, dict] = cast(dict, event.event_info)
        var_info = event_info[ATTR_VAR]

        if (
            address := f"{var_info[ATTR_TYPE]}.{var_info[ATTR_ID]}"
        ) not in self.addresses:
            # New/unknown variable, refresh full set.
            update_task = asyncio.create_task(self.update())
            self.isy.background_tasks.add(update_task)
            update_task.add_done_callback(self.isy.background_tasks.discard)
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
