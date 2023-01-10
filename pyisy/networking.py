"""ISY Network Resources Module."""
from asyncio import sleep
from xml.dom import minidom

from .constants import (
    ATTR_ID,
    PROTO_NETWORK,
    TAG_NAME,
    TAG_NET_RULE,
    URL_NETWORK,
    URL_RESOURCES,
)
from .exceptions import XML_ERRORS, XML_PARSE_ERROR
from .helpers import value_from_xml
from .logging import _LOGGER


class NetworkResources:
    """
    Network Resources class cobject.

    DESCRIPTION:
        This class handles the ISY networking module.

    USAGE:
        This object may be used in a similar way as a
        dictionary with the either networking command
        names or ids being used as keys and the ISY
        networking command class will be returned.

    EXAMPLE:
        # a = networking['test function']
        # a.run()

    ATTRIBUTES:
        isy: The ISY device class
        addresses: List of net command ids
        nnames: List of net command names
        nobjs: List of net command objects

    """

    def __init__(self, isy, xml=None):
        """
        Initialize the network resources class.

        isy: ISY class
        xml: String of xml data containing the configuration data
        """
        self.isy = isy

        self.addresses = []
        self.nnames = []
        self.nobjs = []

        if xml is not None:
            self.parse(xml)

    def parse(self, xml):
        """
        Parse the xml data.

        xml: String of the xml data
        """
        try:
            xmldoc = minidom.parseString(xml)
        except XML_ERRORS:
            _LOGGER.error("%s: NetworkResources, resources not loaded", XML_PARSE_ERROR)
            return

        features = xmldoc.getElementsByTagName(TAG_NET_RULE)
        for feature in features:
            address = int(value_from_xml(feature, ATTR_ID))
            if address not in self.addresses:
                nname = value_from_xml(feature, TAG_NAME)
                nobj = NetworkCommand(self, address, nname)
                self.addresses.append(address)
                self.nnames.append(nname)
                self.nobjs.append(nobj)

        _LOGGER.info("ISY Loaded Network Resources Commands")

    async def update(self, wait_time=0):
        """
        Update the contents of the networking class.

        wait_time: [optional] Amount of seconds to wait before updating
        """
        await sleep(wait_time)
        xml = await self.isy.conn.get_network()
        self.parse(xml)

    async def update_threaded(self, interval):
        """
        Continually update the class until it is told to stop.

        Should be run in a thread.
        """
        while self.isy.auto_update:
            await self.update(interval)

    def __getitem__(self, val):
        """Return the item from the collection."""
        try:
            val = int(val)
            return self.get_by_id(val)
        except (ValueError, KeyError):
            return self.get_by_name(val)

    def __setitem__(self, val, value):
        """Set the item value."""
        return None

    def get_by_id(self, val):
        """
        Return command object being given a command id.

        val: Integer representing command id
        """
        try:
            ind = self.addresses.index(val)
            return self.get_by_index(ind)
        except (ValueError, KeyError):
            return None

    def get_by_name(self, val):
        """
        Return command object being given a command name.

        val: String representing command name
        """
        try:
            ind = self.nnames.index(val)
            return self.get_by_index(ind)
        except (ValueError, KeyError):
            return None

    def get_by_index(self, val):
        """
        Return command object being given a command index.

        val: Integer representing command index in List
        """
        return self.nobjs[val]


class NetworkCommand:
    """
    Network Command Class.

    DESCRIPTION:
        This class handles individual networking commands.

    ATTRIBUTES:
        network_resources: The networkin resources class

    """

    def __init__(self, network_resources, address, name):
        """Initialize network command class.

        network_resources: NetworkResources class
        address: Integer of the command id
        """
        self._network_resources = network_resources
        self.isy = network_resources.isy
        self._id = address
        self._name = name

    @property
    def address(self):
        """Return the Resource ID for the Network Resource."""
        return str(self._id)

    @property
    def name(self):
        """Return the name of this entity."""
        return self._name

    @property
    def protocol(self):
        """Return the Protocol for this node."""
        return PROTO_NETWORK

    async def run(self):
        """Execute the networking command."""
        req_url = self.isy.conn.compile_url([URL_NETWORK, URL_RESOURCES, str(self._id)])

        if not await self.isy.conn.request(req_url, ok404=True):
            _LOGGER.warning("ISY could not run networking command: %s", str(self._id))
            return
        _LOGGER.debug("ISY ran networking command: %s", str(self._id))
