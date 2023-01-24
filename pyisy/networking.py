"""ISY Network Resources Module."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pyisy.constants import TAG_ID, TAG_NAME, URL_NETWORK, URL_RESOURCES, Protocol
from pyisy.helpers.entity import Entity, EntityDetail
from pyisy.helpers.entity_platform import EntityPlatform
from pyisy.helpers.events import EventEmitter
from pyisy.logging import _LOGGER

if TYPE_CHECKING:
    from pyisy.isy import ISY

PLATFORM = "networking"


@dataclass
class NetworkCommandDetail(EntityDetail):
    """Dataclass to hold entity detail info."""

    control_info: dict[str, str | bool] = field(default_factory=dict)
    id: str = ""
    is_modified: bool = False
    name: str = ""


class NetworkResources(EntityPlatform):
    """Network Resources class."""

    def __init__(self, isy: ISY) -> None:
        """
        Initialize the network resources class.

        Iterate over self.values()
        """
        super().__init__(isy=isy, platform_name=PLATFORM)
        self.url = self.isy.conn.compile_url([URL_NETWORK, URL_RESOURCES])

    def parse(self, xml_dict: dict[str, Any]) -> None:
        """Parse the results from the ISY."""
        if not (net_config := xml_dict["net_config"]) or not (
            features := net_config["net_rule"]
        ):
            return
        for feature in features:
            self.parse_entity(feature)

        _LOGGER.info("Loaded network resources commands")

    def parse_entity(self, feature: dict[str, Any]) -> None:
        """Parse a single value and add it to the platform."""
        try:
            address = feature[TAG_ID]
            name = feature[TAG_NAME]
            _LOGGER.debug("Parsing %s: %s (%s)", PLATFORM, name, address)
            detail = NetworkCommandDetail(**feature)
            entity = NetworkCommand(self, address, name, detail)
            self.add_or_update_entity(address, name, entity)
        except (TypeError, KeyError, ValueError) as exc:
            _LOGGER.exception("Error loading %s: %s", PLATFORM, exc)

    async def update_threaded(self, interval: float) -> None:
        """
        Continually update the class until it is told to stop.

        Should be run in a thread.
        """
        while self.isy.auto_update:
            await self.update(interval)


class NetworkCommand(Entity[NetworkCommandDetail, bool]):
    """Network Command Class handles individual networking commands."""

    _status: bool = True

    def __init__(
        self,
        platform: NetworkResources,
        address: str,
        name: str,
        detail: NetworkCommandDetail,
    ):
        """Initialize network command class."""
        self.status_events = EventEmitter()
        self.platform = platform
        self.isy = platform.isy
        self._address = address
        self._name = name
        self._protocol = Protocol.NETWORK
        self.detail = detail

    async def run(self) -> None:
        """Execute the networking command."""
        req_url = self.isy.conn.compile_url([URL_NETWORK, URL_RESOURCES, self.address])

        if not await self.isy.conn.request(req_url, ok404=True):
            # We log this as a warning because the ISY is finicky about response codes.
            #   it may report that it failed, but have worked fine.
            _LOGGER.warning("Could not run networking command: %s", self.address)
            return
        _LOGGER.debug("Ran networking command: %s", self.address)

    def update_entity(self, name: str, detail: NetworkCommandDetail) -> None:
        """Update an entity information."""
        self.detail = detail
