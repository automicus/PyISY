"""Helper functions for the PyISY Module."""
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
        return state, aux_props

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
    mangage DST without significant guessing and effort.
    """
    return datetime.datetime.now()


class EventEmitter:
    """Event Emitter class."""

    def __init__(self):
        """Initialize a new Event Emitter class."""
        self._subscribers = []

    def subscribe(self, callback):
        """Subscribe to the events."""
        listener = EventListener(self, callback)
        self._subscribers.append(listener)
        return listener

    def unsubscribe(self, listener):
        """Unsubscribe from the events."""
        self._subscribers.remove(listener)

    def notify(self, event):
        """Notify a listener."""
        for subscriber in self._subscribers:
            subscriber.callback(event)


class EventListener:
    """Event Listener class."""

    def __init__(self, emitter, callback):
        """Initialize a new Event Listener class."""
        self._emitter = emitter
        self.callback = callback

    def unsubscribe(self):
        """Unsubscribe from the events."""
        self._emitter.unsubscribe(self)


class NodeProperty(dict):
    """Class to hold result of a control event or node aux property."""

    def __init__(
        self,
        control,
        value=ISY_VALUE_UNKNOWN,
        prec=DEFAULT_PRECISION,
        uom=DEFAULT_UNIT_OF_MEASURE,
        formatted=None,
        address=None,
    ):
        """Initialize an control result or aux property."""
        super().__init__(
            self,
            control=control,
            value=value,
            prec=prec,
            uom=uom,
            formatted=(formatted if formatted is not None else value),
            address=address,
        )

    @property
    def address(self):
        """Report the address of the node with this property."""
        return self["address"]

    @property
    def control(self):
        """Report the event control string."""
        return self["control"]

    @property
    def value(self):
        """Report the value, if there was one."""
        return self["value"]

    @property
    def prec(self):
        """Report the precision, if there was one."""
        return self["prec"]

    @property
    def uom(self):
        """Report the unit of measure, if there was one."""
        return self["uom"]

    @property
    def formatted(self):
        """Report the formatted value, if there was one."""
        return self["formatted"]

    def __str__(self):
        """Return just the event title to prevent breaking changes."""
        return (
            f"NodeProperty('{self.address}': control='{self.control}', "
            f"value='{self.value}', prec='{self.prec}', "
            f"uom='{self.uom}', formatted='{self.formatted}')"
        )

    __repr__ = __str__

    def __getattr__(self, name):
        """Retrieve the properties."""
        return self[name]

    def __setattr__(self, name, value):
        """Allow setting of properties."""
        self[name] = value


class ZWaveProperties(dict):
    """Class to hold Z-Wave Product Details from a Z-Wave Node."""

    def __init__(self, xml=None):
        """Initialize an control result or aux property."""
        category = None
        devtype_mfg = None
        devtype_gen = None
        basic_type = 0
        generic_type = 0
        specific_type = 0
        mfr_id = 0
        prod_type_id = 0
        product_id = 0
        self._raw = ""

        if xml:
            category = value_from_xml(xml, TAG_CATEGORY)
            devtype_mfg = value_from_xml(xml, TAG_MFG)
            devtype_gen = value_from_xml(xml, TAG_GENERIC)
            self._raw = xml.toxml()
        if devtype_gen:
            (basic_type, generic_type, specific_type) = devtype_gen.split(".")
        if devtype_mfg:
            (mfr_id, prod_type_id, product_id) = devtype_mfg.split(".")

        super().__init__(
            self,
            category=category,
            devtype_mfg=devtype_mfg,
            devtype_gen=devtype_gen,
            basic_type=basic_type,
            generic_type=generic_type,
            specific_type=specific_type,
            mfr_id=mfr_id,
            prod_type_id=prod_type_id,
            product_id=product_id,
        )

    @property
    def category(self):
        """Return the ISY Z-Wave Category Property."""
        return self["category"]

    @property
    def devtype_mfg(self):
        """Return the Full Devtype Mfg Z-Wave Property String."""
        return self["devtype_mfg"]

    @property
    def devtype_gen(self):
        """Return the Full Devtype Generic Z-Wave Property String."""
        return self["devtype_gen"]

    @property
    def basic_type(self):
        """Return the Z-Wave basic type Property."""
        return self["basic_type"]

    @property
    def generic_type(self):
        """Return the Z-Wave generic type Property."""
        return self["generic_type"]

    @property
    def specific_type(self):
        """Return the Z-Wave specific type Property."""
        return self["specific_type"]

    @property
    def mfr_id(self):
        """Return the Z-Wave Manufacterer ID Property."""
        return self["mfr_id"]

    @property
    def prod_type_id(self):
        """Return the Z-Wave Product Type ID Property."""
        return self["prod_type_id"]

    @property
    def product_id(self):
        """Return the Z-Wave Product ID Property."""
        return self["product_id"]

    def __str__(self):
        """Return just the original raw xml string from the ISY."""
        return f"ZWaveProperties({self._raw})"

    __repr__ = __str__

    def __getattr__(self, name):
        """Retrieve the properties."""
        return self[name]

    def __setattr__(self, name, value):
        """Allow setting of properties."""
        self[name] = value
