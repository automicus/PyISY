"""XML Helper Functions."""
from __future__ import annotations

from typing import cast
from xml.dom import minidom

import xmltodict

from pyisy.exceptions import (
    XML_ERRORS,
    XML_PARSE_ERROR,
    ISYResponseError,
    ISYResponseParseError,
)


def parse_xml(xml: str | None) -> dict:
    """Parse an XML string and return a dict object."""
    if not xml:
        raise ISYResponseError("Could not load response")

    try:
        xml_dict = xmltodict.parse(xml)
    except XML_ERRORS as exc:
        raise ISYResponseParseError(XML_PARSE_ERROR) from exc
    return cast(dict, xml_dict)


def value_from_xml(xml: minidom.Element, tag_name: str, default: str = "") -> str:
    """Extract a value from the XML element."""
    value = default
    try:
        value = xml.getElementsByTagName(tag_name)[0].firstChild.toxml()
    except XML_ERRORS:
        pass
    return value


def attr_from_xml(
    xml: minidom.Element, tag_name: str, attr_name: str, default: str = ""
) -> str:
    """Extract an attribute value from the raw XML."""
    value = default
    try:
        root = xml.getElementsByTagName(tag_name)[0]
        value = attr_from_element(root, attr_name, default)
    except XML_ERRORS:
        pass
    return value


def attr_from_element(
    element: minidom.Element, attr_name: str, default: str = ""
) -> str:
    """Extract an attribute value from an XML element."""
    value = default
    attributes: minidom.NamedNodeMap = element.attributes
    if attr_name in attributes.keys():  # type: ignore[no-untyped-call]
        value = attributes[attr_name].value
    return value


def value_from_nested_xml(
    base: minidom.Element, chain: list[str], default: str = ""
) -> str:
    """Extract a value from multiple nested tags."""
    value = default
    result = None
    try:
        result = base.getElementsByTagName(chain[0])[0]
        if len(chain) > 1:
            result = result.getElementsByTagName(chain[1])[0]
        if len(chain) > 2:
            result = result.getElementsByTagName(chain[2])[0]
        if len(chain) > 3:
            result = result.getElementsByTagName(chain[3])[0]
        value = result.firstChild.toxml()
    except XML_ERRORS:
        pass
    return value
