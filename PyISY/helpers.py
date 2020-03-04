"""Helper functions for the PyISY Module."""
import datetime
import time

from .constants import (
    ATTR_FORMATTED,
    ATTR_ID,
    ATTR_PREC,
    ATTR_UOM,
    ATTR_VALUE,
    BATLVL_PROPERTY,
    ISY_EPOCH_OFFSET,
    STATE_PROPERTY,
    VALUE_UNKNOWN,
)


def parse_xml_properties(xmldoc):
    """
    Parse the xml properties string.

    Args:
        xmldoc: xml document to parse

    Returns:
        (state_val, state_uom, state_prec, aux_props)

    """
    aux_props = {}
    state_set = False
    state = {}

    props = xmldoc.getElementsByTagName("property")
    if not props:
        return {}, {}

    for prop in props:
        prop_id = attr_from_element(prop, ATTR_ID)
        uom = attr_from_element(prop, ATTR_UOM, "")
        val = attr_from_element(prop, ATTR_VALUE, "").strip()
        prec = attr_from_element(prop, ATTR_PREC, "0")
        formatted = attr_from_element(prop, ATTR_FORMATTED, val)

        # ISY firmwares < 5 return a list of possible units.
        # ISYv5+ returns a UOM string which is checked against the SDK.
        # Only return a list if the UOM should be a list.
        if "/" in uom and uom != "n/a":
            uom = uom.split("/")

        val = int(val) if val != "" else VALUE_UNKNOWN

        result = {
            ATTR_ID: prop_id,
            ATTR_VALUE: val,
            ATTR_PREC: prec,
            ATTR_UOM: uom,
            ATTR_FORMATTED: formatted,
        }

        if prop_id == STATE_PROPERTY:
            state = result
            state_set = True
        elif prop_id == BATLVL_PROPERTY and not state_set:
            state = result
        else:
            aux_props[prop_id] = result

    return state, aux_props


def value_from_xml(xml, tag_name, default=None):
    """Extract a value from the XML element."""
    value = default
    try:
        value = xml.getElementsByTagName(tag_name)[0].firstChild.toxml()
    except (IndexError, AttributeError):
        pass
    return value


def attr_from_xml(xml, tag_name, attr_name, default=None):
    """Extract an attribute value from the raw XML."""
    value = default
    try:
        root = xml.getElementsByTagName(tag_name)[0]
        value = attr_from_element(root, attr_name, default)
    except (IndexError, AttributeError):
        pass
    return value


def attr_from_element(element, attr_name, default=None):
    """Extract an attribute value from an XML element."""
    value = default
    if attr_name in element.attributes.keys():
        value = element.attributes[attr_name].value
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
