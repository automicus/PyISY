"""ISY Network Resources Module."""
from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from pyisy.constants import (
    PROTO_NETWORK,
    TAG_ID,
    TAG_NAME,
    TAG_NET_RULE,
    URL_NETWORK,
    URL_RESOURCES,
)
from pyisy.helpers.entity import Entity
from pyisy.helpers.entity_platform import EntityPlatform
from pyisy.helpers.events import EventEmitter
from pyisy.logging import _LOGGER

if TYPE_CHECKING:
    from pyisy.isy import ISY

PLATFORM = "networking"


class NetworkResources(EntityPlatform):
    """Network Resources class."""

    def __init__(self, isy: ISY) -> None:
        """
        Initialize the network resources class.

        Iterate over self.values()
        """
        super().__init__(isy=isy, platform_name=PLATFORM)
        self.url = self.isy.conn.compile_url([URL_NETWORK, URL_RESOURCES])

    async def parse(self, xml_dict: dict[str, Any]) -> None:
        """Parse the results from the ISY."""
        features = xml_dict["NetConfig"][TAG_NET_RULE]
        for feature in features:
            address = feature[TAG_ID]
            name = feature[TAG_NAME]
            detail = copy.deepcopy(feature)
            entity = NetworkCommand(self, address, name, detail)
            await self.add_or_update_entity(address, name, entity)

        _LOGGER.info("ISY Loaded Network Resources Commands")

    async def update_threaded(self, interval):
        """
        Continually update the class until it is told to stop.

        Should be run in a thread.
        """
        while self.isy.auto_update:
            await self.update(interval)


class NetworkCommand(Entity):
    """
    Network Command Class.

    DESCRIPTION:
        This class handles individual networking commands.

    ATTRIBUTES:
        network_resources: The networking resources class

    """

    def __init__(
        self, platform: NetworkResources, address: str, name: str, detail: dict
    ):
        """Initialize network command class."""
        self.status_events = EventEmitter()
        self.platform = platform
        self.isy = platform.isy
        self._address = address
        self._name = name
        self._protocol = PROTO_NETWORK
        self.detail = detail

    async def run(self):
        """Execute the networking command."""
        req_url = self.isy.conn.compile_url([URL_NETWORK, URL_RESOURCES, self.address])

        if not await self.isy.conn.request(req_url, ok404=True):
            _LOGGER.warning("ISY could not run networking command: %s", self.address)
            return
        _LOGGER.debug("ISY ran networking command: %s", self.address)
