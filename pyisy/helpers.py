"""Helper functions for the PyISY Module."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, is_dataclass
import datetime
import time

from .constants import (
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
    TAG_CATEGORY,
    TAG_GENERIC,
    TAG_MFG,
    TAG_PROPERTY,
    UOM_SECONDS,
)
from .exceptions import XML_ERRORS
from .logging import _LOGGER


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
    state = NodeProperty(PROP_STATUS, uom=ISY_PROP_NOT_SET)

    props = xmldoc.getElementsByTagName(TAG_PROPERTY)
    if not props:
        return state, aux_props, state_set

    for prop in props:
        prop_id = attr_from_element(prop, ATTR_ID)
        uom = attr_from_element(prop, ATTR_UNIT_OF_MEASURE, DEFAULT_UNIT_OF_MEASURE)
        value = attr_from_element(prop, ATTR_VALUE, "").strip()
        prec = attr_from_element(prop, ATTR_PRECISION, DEFAULT_PRECISION)
        formatted = attr_from_element(prop, ATTR_FORMATTED, value)

        # ISY firmwares < 5 return a list of possible units.
        # ISYv5+ returns a UOM string which is checked against the SDK.
        # Only return a list if the UOM should be a list.
        if "/" in uom and uom != "n/a":
            uom = uom.split("/")

        value = int(value) if value.strip() != "" else ISY_VALUE_UNKNOWN

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

    return state, aux_props, state_set


def value_from_xml(xml, tag_name, default=None):
    """Extract a value from the XML element."""
    value = default
    try:
        value = xml.getElementsByTagName(tag_name)[0].firstChild.toxml()
    except XML_ERRORS:
        pass
    return value


def attr_from_xml(xml, tag_name, attr_name, default=None):
    """Extract an attribute value from the raw XML."""
    value = default
    try:
        root = xml.getElementsByTagName(tag_name)[0]
        value = attr_from_element(root, attr_name, default)
    except XML_ERRORS:
        pass
    return value


def attr_from_element(element, attr_name, default=None):
    """Extract an attribute value from an XML element."""
    value = default
    if attr_name in element.attributes.keys():
        value = element.attributes[attr_name].value
    return value


def value_from_nested_xml(base, chain, default=None):
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


def now():
    """Get the current system time.

    Note: this module uses naive datetimes because the
    ISY is highly inconsistent with time conventions
    and does not present enough information to accurately
    manage DST without significant guessing and effort.
    """
    return datetime.datetime.now()


class EventEmitter:
    """Event Emitter class."""

    _subscribers: list[EventListener]

    def __init__(self):
        """Initialize a new Event Emitter class."""
        self._subscribers = []

    def subscribe(
        self, callback: Callable, event_filter: dict | str = None, key: str = None
    ):
        """Subscribe to the events."""
        listener = EventListener(
            emitter=self, callback=callback, event_filter=event_filter, key=key
        )
        self._subscribers.append(listener)
        return listener

    def unsubscribe(self, listener):
        """Unsubscribe from the events."""
        self._subscribers.remove(listener)

    def notify(self, event):
        """Notify a listener."""
        for subscriber in self._subscribers:
            # Guard against downstream errors interrupting the socket connection (#249)
            try:
                if e_filter := subscriber.event_filter:
                    if is_dataclass(event) and isinstance(e_filter, dict):
                        if not (e_filter.items() <= event.__dict__.items()):
                            continue
                    elif event != e_filter:
                        continue

                if subscriber.key:
                    subscriber.callback(event, subscriber.key)
                    continue
                subscriber.callback(event)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Error during callback of %s", event)


@dataclass
class EventListener:
    """Event Listener class."""

    emitter: EventEmitter
    callback: Callable
    event_filter: dict | str
    key: str

    def unsubscribe(self):
        """Unsubscribe from the events."""
        self.emitter.unsubscribe(self)


@dataclass
class NodeProperty:
    """Class to hold result of a control event or node aux property."""

    control: str
    value: int | float = ISY_VALUE_UNKNOWN
    prec: str = DEFAULT_PRECISION
    uom: str = DEFAULT_UNIT_OF_MEASURE
    formatted: str = None
    address: str = None


@dataclass
class ZWaveProperties:
    """Class to hold Z-Wave Product Details from a Z-Wave Node."""

    category: str = "0"
    devtype_mfg: str = "0.0.0"
    devtype_gen: str = "0.0.0"
    basic_type: str = "0"
    generic_type: str = "0"
    specific_type: str = "0"
    mfr_id: str = "0"
    prod_type_id: str = "0"
    product_id: str = "0"
    raw: str = ""

    @classmethod
    def from_xml(cls, xml):
        """Return a Z-Wave Properties class from an xml DOM object."""
        category = value_from_xml(xml, TAG_CATEGORY)
        devtype_mfg = value_from_xml(xml, TAG_MFG)
        devtype_gen = value_from_xml(xml, TAG_GENERIC)
        raw = xml.toxml()
        basic_type = "0"
        generic_type = "0"
        specific_type = "0"
        mfr_id = "0"
        prod_type_id = "0"
        product_id = "0"
        if devtype_gen:
            (basic_type, generic_type, specific_type) = devtype_gen.split(".")
        if devtype_mfg:
            (mfr_id, prod_type_id, product_id) = devtype_mfg.split(".")

        return ZWaveProperties(
            category=category,
            devtype_mfg=devtype_mfg,
            devtype_gen=devtype_gen,
            basic_type=basic_type,
            generic_type=generic_type,
            specific_type=specific_type,
            mfr_id=mfr_id,
            prod_type_id=prod_type_id,
            product_id=product_id,
            raw=raw,
        )
