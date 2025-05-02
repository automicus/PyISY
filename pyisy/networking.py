"""ISY Network Resources Module."""

from __future__ import annotations

from asyncio import sleep
from typing import TYPE_CHECKING
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

if TYPE_CHECKING:
    from .isy import ISY


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

    def __init__(self, isy: ISY, xml: str | None = None) -> None:
        """
        Initialize the network resources class.

        isy: ISY class
        xml: String of xml data containing the configuration data
        """
        self.isy = isy

        self.addresses: list[int] = []
        self._address_index: dict[int, int] = {}
        self.nnames: list[str] = []
        self.nobjs: list[NetworkCommand] = []

        if xml is not None:
            self.parse(xml)

    def parse(self, xml: str) -> None:
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
            if address in self._address_index:
                continue
            nname = value_from_xml(feature, TAG_NAME)
            nobj = NetworkCommand(self, address, nname)
            self.addresses.append(address)
            self._address_index[address] = len(self.addresses) - 1
            self.nnames.append(nname)
            self.nobjs.append(nobj)

        _LOGGER.info("ISY Loaded Network Resources Commands")

    async def update(self, wait_time: int = 0) -> None:
        """
        Update the contents of the networking class.

        wait_time: [optional] Amount of seconds to wait before updating
        """
        await sleep(wait_time)
        xml = await self.isy.conn.get_network()
        self.parse(xml)

    async def update_threaded(self, interval: int) -> None:
        """
        Continually update the class until it is told to stop.

        Should be run in a thread.
        """
        while self.isy.auto_update:
            await self.update(interval)

    def __getitem__(self, val: str | int) -> NetworkCommand | None:
        """Return the item from the collection."""
        try:
            val = int(val)
            return self.get_by_id(val)
        except (ValueError, KeyError):
            return self.get_by_name(val)

    def __setitem__(self, val, value):
        """Set the item value."""
        return

    def get_by_id(self, val: int) -> NetworkCommand | None:
        """
        Return command object being given a command id.

        val: Integer representing command id
        """
        ind = self._address_index.get(val)
        return None if ind is None else self.get_by_index(ind)

    def get_by_name(self, val: str) -> NetworkCommand | None:
        """
        Return command object being given a command name.

        val: String representing command name
        """
        try:
            ind = self.nnames.index(val)
            return self.get_by_index(ind)
        except (ValueError, KeyError):
            return None

    def get_by_index(self, val: int) -> NetworkCommand | None:
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

    def __init__(self, network_resources: NetworkResources, address: int, name: str) -> None:
        """Initialize network command class.

        network_resources: NetworkResources class
        address: Integer of the command id
        """
        self._network_resources = network_resources
        self.isy = network_resources.isy
        self._id = address
        self._name = name

    @property
    def address(self) -> str:
        """Return the Resource ID for the Network Resource."""
        return str(self._id)

    @property
    def name(self) -> str:
        """Return the name of this entity."""
        return self._name

    @property
    def protocol(self) -> str:
        """Return the Protocol for this node."""
        return PROTO_NETWORK

    async def run(self) -> None:
        """Execute the networking command."""
        address = self.address
        req_url = self.isy.conn.compile_url([URL_NETWORK, URL_RESOURCES, address])

        if not await self.isy.conn.request(req_url, ok404=True):
            _LOGGER.warning("ISY could not run networking command: %s", address)
            return
        _LOGGER.debug("ISY ran networking command: %s", address)
