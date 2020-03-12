"""Helper functions for the PyISY Module."""
import datetime
import time

from .constants import (
    ATTR_FORMATTED,
    ATTR_ID,
    ATTR_PRECISION,
    ATTR_UNIT_OF_MEASURE,
    ATTR_VALUE,
    INSTEON_RAMP_RATES,
    ISY_EPOCH_OFFSET,
    ISY_VALUE_UNKNOWN,
    PROP_BATTERY_LEVEL,
    PROP_RAMP_RATE,
    PROP_STATUS,
    TAG_PROPERTY,
    UOM_SECONDS,
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
    state = NodeProperty(PROP_STATUS)

    props = xmldoc.getElementsByTagName(TAG_PROPERTY)
    if not props:
        return state, aux_props

    for prop in props:
        prop_id = attr_from_element(prop, ATTR_ID)
        uom = attr_from_element(prop, ATTR_UNIT_OF_MEASURE, "")
        value = attr_from_element(prop, ATTR_VALUE, "").strip()
        prec = attr_from_element(prop, ATTR_PRECISION, "0")
        formatted = attr_from_element(prop, ATTR_FORMATTED, value)

        # ISY firmwares < 5 return a list of possible units.
        # ISYv5+ returns a UOM string which is checked against the SDK.
        # Only return a list if the UOM should be a list.
        if "/" in uom and uom != "n/a":
            uom = uom.split("/")

        value = int(value) if value != "" else ISY_VALUE_UNKNOWN

        result = NodeProperty(prop_id, value, prec, uom, formatted)

        if prop_id == PROP_STATUS:
            state = result
            state_set = True
        elif prop_id == PROP_BATTERY_LEVEL and not state_set:
            state = result
        else:
            if prop_id == PROP_RAMP_RATE:
                result.value = INSTEON_RAMP_RATES.get(value, value)
                result.uom = UOM_SECONDS
            aux_props[prop_id] = result

    return state, aux_props


def value_from_xml(xml, tag_name, default=None):
    """Extract a value from the XML element."""
    value = default
    try:
        value = xml.getElementsByTagName(tag_name)[0].firstChild.toxml()
    except (AttributeError, KeyError, ValueError, TypeError, IndexError):
        pass
    return value


def attr_from_xml(xml, tag_name, attr_name, default=None):
    """Extract an attribute value from the raw XML."""
    value = default
    try:
        root = xml.getElementsByTagName(tag_name)[0]
        value = attr_from_element(root, attr_name, default)
    except (AttributeError, KeyError, ValueError, TypeError, IndexError):
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


class NodeProperty(dict):
    """Class to hold result of a control event or node aux property."""

    def __init__(
        self, control, value=ISY_VALUE_UNKNOWN, prec="0", uom="", formatted=None
    ):
        """Initialize an control result or aux property."""
        super().__init__(
            self, control=control, value=value, prec=prec, uom=uom, formatted=formatted
        )
        self._control = control
        self._value = value
        self._prec = prec
        self._uom = uom
        self._formatted = formatted if formatted is not None else value

    @property
    def control(self):
        """Report the event control string."""
        return self._control

    @property
    def value(self):
        """Report the value, if there was one."""
        return self._value

    @property
    def prec(self):
        """Report the precision, if there was one."""
        return self._prec

    @property
    def uom(self):
        """Report the unit of measure, if there was one."""
        return self._uom

    @property
    def formatted(self):
        """Report the formatted value, if there was one."""
        return self._formatted

    def __str__(self):
        """Return just the event title to prevent breaking changes."""
        return (
            f"'{self.control}': value='{self.value}' "
            f"prec='{self.prec}' uom='{self.uom}' formatted='{self.formatted}'"
        )

    __repr__ = f"NodeProperty({__str__})"

    def __getattr__(self, name):
        """Retreive the properties."""
        return self[name]

    def __setattr__(self, name, value):
        """Allow setting of properties."""
        self[name] = value
