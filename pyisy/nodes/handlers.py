"""Node Event Handler Classes."""

from ..constants import TAG_CATEGORY, TAG_GENERIC, TAG_MFG
from ..helpers import value_from_xml


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
