"""XML Helper Functions."""
from __future__ import annotations

import re
from typing import Any, cast

from dateutil import parser
import xmltodict

# from .timeit import timeit
from pyisy.exceptions import (
    XML_ERRORS,
    XML_PARSE_ERROR,
    ISYResponseError,
    ISYResponseParseError,
)

SNAKE = re.compile(r"(?<!^)(?=[A-Z])")


def post_processor(path: str, key: str, value: Any) -> tuple[str, Any]:
    """Post-process XML Dict to snake case keys and interpret strings."""
    # Convert boolean
    if value == "true":
        value = True
    if value == "false":
        value = False

    # Make keys `snake_case`
    key = SNAKE.sub("_", key).lower()

    # Rename some keys
    if key == "property":  # Use full word
        key = "prop"
    elif key == "type":  # Avoid overwriting default methods
        key = "type_"
    elif key == "parent_id":  # Make programs consistent with nodes
        key = "parent"
    elif key == "cat":  # Use full word
        key = "category"

    # Convert common keys
    if key == "prec":  # Use full word, make integer
        key = "precision"
        value = int(cast(str, value))
    elif key == "_value":  # Make CData text an integer
        key = "value"
        try:
            value = int(cast(str, value))
        except ValueError:
            pass
    elif key == "flag":
        try:
            value = int(cast(str, value))
        except ValueError:
            pass

    # Convert known dates
    if (key.endswith("_time") or key == "ts") and value is not None:
        try:
            value = parser.parse(cast(str, value))
        except ValueError:
            pass

    return key, value


# @timeit
def parse_xml(
    xml: str | None,
    attr_prefix: str | None = "",
    cdata_key: str | None = "_value",
    use_pp: bool | None = True,
) -> dict:
    """Parse an XML string and return a dict object."""
    if not xml:
        raise ISYResponseError("Could not load response")
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
        raise ISYResponseParseError(XML_PARSE_ERROR) from exc
    return cast(dict, xml_dict)
