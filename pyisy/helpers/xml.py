"""XML Helper Functions."""
from __future__ import annotations

from contextlib import suppress
import re
from typing import Any, cast

from dateutil import parser
import xmltodict

from pyisy.constants import (
    ATTR_FLAG,
    ATTR_TYPE,
    TAG_PARENT,
    TAG_PROPERTY,
    TAG_VALUE,
    XML_FALSE,
    XML_TRUE,
)
from pyisy.exceptions import (
    XML_ERRORS,
    XML_PARSE_ERROR,
    ISYResponseError,
    ISYResponseParseError,
)
from pyisy.logging import _LOGGER

SNAKE = re.compile(r"((?<=[a-z0-9])[A-Z]|(?!^)[A-Z](?=[a-z]))")


def post_processor(path: str, key: str, value: Any) -> tuple[str, Any]:
    """Post-process XML Dict to snake case keys and interpret strings."""
    # Convert boolean
    if value == XML_TRUE:
        value = True
    if value == XML_FALSE:
        value = False

    # Make keys `snake_case`
    key = SNAKE.sub(r"_\1", key).lower()

    # Rename some keys
    if key == "prop":  # Use full word
        key = TAG_PROPERTY
    elif key == "type":  # Avoid overwriting default methods
        key = ATTR_TYPE
    elif key == "parent_id":  # Make programs consistent with nodes
        key = TAG_PARENT
    elif key == "cat":  # Use full word
        key = "category"
    elif key == "encode_ur_ls":  # Fix bad CamelCase
        key = "encode_urls"

    # Convert common keys
    if key == "prec":  # Use full word, make integer
        key = "precision"
        value = int(cast(str, value))
    elif key == "_value":  # Make CData text an integer
        key = TAG_VALUE
        with suppress(ValueError):
            value = int(cast(str, value))
    elif key == ATTR_FLAG:
        with suppress(ValueError):
            value = int(cast(str, value))
    # Convert known dates
    if (key.endswith("_time") or key == "ts") and value is not None:
        with suppress(ValueError):
            value = parser.parse(cast(str, value))

    return key, value


def parse_xml(
    xml: str | None,
    raise_on_error: bool = False,
    attr_prefix: str | None = "",
    cdata_key: str | None = "_value",
    use_pp: bool | None = True,
) -> dict:
    """Parse an XML string and return a dict object."""
    if not xml:
        if raise_on_error:
            raise ISYResponseError("Could not load response")
        _LOGGER.error("Could not load response")
        return {}
    post = post_processor if use_pp else None
    try:
        xml_dict = xmltodict.parse(
            xml,
            attr_prefix=attr_prefix,
            cdata_key=cdata_key,
            postprocessor=post,
            dict_constructor=dict,
        )
    except XML_ERRORS as exc:
        if raise_on_error:
            raise ISYResponseParseError(XML_PARSE_ERROR) from exc
        _LOGGER.error(XML_PARSE_ERROR)
        return {}
    return cast(dict, xml_dict)
