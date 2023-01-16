"""Parser functions for ISY/IoX Nodes."""
from __future__ import annotations

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
    ISY_PROP_NOT_SET,
    ISY_VALUE_UNKNOWN,
    PROP_BATTERY_LEVEL,
    PROP_RAMP_RATE,
    PROP_STATUS,
    TAG_PROPERTY,
    UOM_SECONDS,
)
from pyisy.helpers.models import NodeProperty
from pyisy.helpers.xml import attr_from_element


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
