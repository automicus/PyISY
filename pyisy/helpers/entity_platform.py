"""Base class for the different ISY/IoX sub-platforms.

This has been adapted from home-assistant/core:
homeassistant.helpers.entity_platform
"""
from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from collections.abc import Iterable, ValuesView
import json
from typing import TYPE_CHECKING, Any, Protocol, TypeVar

from pyisy.helpers.entity import Entity
from pyisy.helpers.events import EventEmitter
from pyisy.helpers.xml import parse_xml
from pyisy.logging import _LOGGER, LOG_VERBOSE

if TYPE_CHECKING:
    from pyisy.isy import ISY

T = TypeVar("T")


class AddEntitiesCallback(Protocol):
    """Protocol type for EntityPlatform.add_entities callback."""

    def __call__(
        self, new_entities: Iterable[Entity], update_before_add: bool = False
    ) -> None:
        """Define add_entities type."""


class EntityPlatformModule(Protocol):
    """Protocol type for entity platform modules."""

    async def async_setup_platform(
        self,
        isy: ISY,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up an integration platform async."""


class EntityPlatform(ABC):
    """Manage the entities for a single platform."""

    loaded: bool = False
    status_events: EventEmitter
    names: list[str] = []
    addresses: list[str] = []
    entities: dict[str, Entity] = {}
    url: str

    def __init__(
        self,
        *,
        isy: ISY,
        platform_name: str,
    ) -> None:
        """Initialize the entity platform."""
        self.isy = isy
        self.platform_name = platform_name
        self.entities: dict[str, Entity] = {}
        self._tasks: list[asyncio.Task[None]] = []
        # Stop tracking tasks after setup is completed
        self._setup_complete = False
        self.status_events = EventEmitter()

    def __repr__(self) -> str:
        """Represent an EntityPlatform."""
        return f"<EntityPlatform platform={self.platform_name} entities={len(self.entities)}>"

    async def update(self, wait_time: float = 0) -> None:
        """Update the contents of the class."""
        await asyncio.sleep(wait_time)
        xml_dict = parse_xml(await self.isy.conn.request(self.url), attr_prefix="")
        _LOGGER.log(
            LOG_VERBOSE,
            "%s:\n%s",
            self.url,
            json.dumps(xml_dict, indent=4, sort_keys=True, default=str),
        )
        await self.parse(xml_dict)
        self.loaded = True

    @abstractmethod
    async def parse(self, xml_dict: dict[str, Any]) -> None:
        """Parse the results from the ISY.

        This method should be overloaded in the child class.
        """
        raise NotImplementedError()

    async def add_or_update_entity(
        self, address: str, name: str, entity: Entity
    ) -> None:
        """Add or update an entity on the platform."""
        # FUTURE: May need to support a compare function callback
        if address in self.addresses:
            if entity.detail != self.entities[address].detail:
                self.names[self.addresses.index(address)] = name
                self.entities[address].update_entity(name, entity.detail)
                self.status_events.notify("NEED CHANGE EVENT")
            return

        self.addresses.append(address)
        self.names.append(name)
        self.entities[address] = entity
        self.status_events.notify("NEED NEW ENTITY EVENT")

    def __getitem__(self, key: str) -> Entity | None:
        """Return the item from the collection."""
        if key in self.addresses:
            return self.entities[key]
        if key in self.names:
            i = self.names.index(key)
            return self.entities[self.addresses[i]]
        return None

    def __setitem__(self, key: str, value: Any) -> None:
        """Set the item value (Not supported)."""
        return None

    def values(self) -> ValuesView:
        """Return the underlying values to avoid __iter__ overhead."""
        return self.entities.values()

    def get_by_id(self, key: str) -> Entity | None:
        """Return entity given an address."""
        if key in self.addresses:
            return self.entities[key]
        return None

    def get_by_name(self, key: str) -> Entity | None:
        """Return entity given a name."""
        if key in self.names:
            i = self.names.index(key)
            return self.entities[self.addresses[i]]
        return None

    def get_by_index(self, value: int) -> Entity | None:
        """Return entity given an index."""
        if not (0 <= value <= len(self.addresses)):
            return None
        return list(self.entities.values())[value]
