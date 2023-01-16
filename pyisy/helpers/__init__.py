"""Helper functions for the PyISY Module."""
from __future__ import annotations

import datetime
import time
from typing import TYPE_CHECKING
from xml.dom import minidom

from pyisy.constants import (
    ATTR_FORMATTED,
    ATTR_ID,
    ATTR_PRECISION,
    ATTR_UNIT_OF_MEASURE,
    ATTR_VALUE,
    DEFAULT_PRECISION,
    DEFAULT_UNIT_OF_MEASURE,
    INSTEON_RAMP_RATES,
    ISY_EPOCH_OFFSET,
    ISY_PROP_NOT_SET,
    ISY_VALUE_UNKNOWN,
    PROP_BATTERY_LEVEL,
    PROP_RAMP_RATE,
    PROP_STATUS,
    TAG_PROPERTY,
    UOM_SECONDS,
)
from pyisy.exceptions import XML_ERRORS

if TYPE_CHECKING:
    from pyisy.helpers.models import NodeProperty


def parse_xml_properties(xmldoc: minidom.Element):
    """
    Parse the xml properties string.

    Args:
        xmldoc: xml document to parse

    Returns:
        (state_val, state_uom, state_prec, aux_props)

    """
    aux_props: dict[str, NodeProperty] = {}
    state_set: bool = False
    state: NodeProperty = NodeProperty(PROP_STATUS, uom=ISY_PROP_NOT_SET)

    props = xmldoc.getElementsByTagName(TAG_PROPERTY)
    if not props:
        return state, aux_props, state_set

    for prop in props:
        prop_id = attr_from_element(prop, ATTR_ID)
        uom = attr_from_element(prop, ATTR_UNIT_OF_MEASURE, DEFAULT_UNIT_OF_MEASURE)
        value_str = attr_from_element(prop, ATTR_VALUE, "").strip()
        prec = attr_from_element(prop, ATTR_PRECISION, DEFAULT_PRECISION)
        formatted = attr_from_element(prop, ATTR_FORMATTED, value_str)

        # ISY firmwares < 5 return a list of possible units.
        # ISYv5+ returns a UOM string which is checked against the SDK.
        # Only return a list if the UOM should be a list.
        uom_list: list[str] = []
        if "/" in uom and uom != "n/a":
            uom_list = uom.split("/")

        value = int(value_str) if value_str.strip() != "" else ISY_VALUE_UNKNOWN

        result = NodeProperty(
            prop_id, value, prec, uom_list if uom_list else uom, formatted
        )

        if prop_id == PROP_STATUS:
            state = result
            state_set = True
        elif prop_id == PROP_BATTERY_LEVEL and not state_set:
            state = result
        else:
            if prop_id == PROP_RAMP_RATE:
                result.value = INSTEON_RAMP_RATES.get(value_str, value)
                result.uom = UOM_SECONDS
            aux_props[prop_id] = result

    return state, aux_props, state_set


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
    if attr_name in element.attributes.keys():
        value = element.attributes[attr_name].value
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


def ntp_to_system_time(timestamp):
    """Convert a ISY NTP time to system UTC time.

    Adapted from Python ntplib module.
    https://pypi.org/project/ntplib/

    Parameters:
    timestamp -- timestamp in NTP time

    Returns:
    corresponding system time

    Note: The ISY uses a EPOCH_OFFSET in addition to standard NTP.

    """
    _system_epoch = datetime.date(*time.gmtime(0)[0:3])
    _ntp_epoch = datetime.date(1900, 1, 1)
    ntp_delta = ((_system_epoch - _ntp_epoch).days * 24 * 3600) - ISY_EPOCH_OFFSET

    return datetime.datetime.fromtimestamp(timestamp - ntp_delta)


def now() -> datetime.datetime:
    """Get the current system time.

    Note: this module uses naive datetimes because the
    ISY is highly inconsistent with time conventions
    and does not present enough information to accurately
    manage DST without significant guessing and effort.
    """
    return datetime.datetime.now()
