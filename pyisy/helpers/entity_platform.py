"""Base class for the different ISY/IoX sub-platforms.

This has been adapted from home-assistant/core:
homeassistant.helpers.entity_platform
"""
from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from collections.abc import Iterable, ValuesView
from dataclasses import asdict, dataclass, field
import json
from typing import TYPE_CHECKING, Any, Generic, Protocol, TypeVar

from pyisy.constants import DEFAULT_DIR, Protocol as EntityProtocol
from pyisy.helpers.entity import Entity, EntityT
from pyisy.helpers.events import EventEmitter
from pyisy.helpers.xml import parse_xml
from pyisy.logging import _LOGGER, LOG_VERBOSE
from pyisy.util.backports import StrEnum
from pyisy.util.output import write_to_file

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


class EntityPlatform(ABC, Generic[EntityT]):
    """Manage the entities for a single platform."""

    loaded: bool = False
    status_events: EventEmitter
    names: list[str]
    addresses: list[str]
    entities: dict[str, EntityT]
    types: list[str]
    url: str
    platform_name: str

    # Parser options
    _parse_attr_prefix: str = ""
    _parse_cdata_key: str = "_value"
    _parse_use_pp: bool = True
    _parse_raise_on_error: bool = False

    def __init__(
        self,
        *,
        isy: ISY,
        platform_name: str,
    ) -> None:
        """Initialize the entity platform."""
        self.isy = isy
        self.platform_name = platform_name

        self.loaded = False

        self.names = []
        self.addresses = []
        self.entities = {}
        self.types = []
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
        xml_dict = parse_xml(
            await self.isy.conn.request(self.url),
            raise_on_error=self._parse_raise_on_error,
            attr_prefix=self._parse_attr_prefix,
            cdata_key=self._parse_cdata_key,
            use_pp=self._parse_use_pp,
        )
        _LOGGER.log(
            LOG_VERBOSE,
            "%s:\n%s",
            self.url,
            json.dumps(xml_dict, indent=4, sort_keys=True, default=str),
        )

        # Write nodes to file for debugging:
        if self.isy.args is not None and self.isy.args.file:
            await self.isy.loop.run_in_executor(
                None,
                write_to_file,
                xml_dict,
                f"{DEFAULT_DIR}rest-{self.platform_name}.json",
            )

        self.parse(xml_dict)
        self.loaded = True

    @abstractmethod
    def parse(self, xml_dict: dict[str, Any]) -> None:
        """Parse the results from the ISY.

        This method should be overloaded in the child class.
        """
        raise NotImplementedError()

    def add_or_update_entity(self, address: str, name: str, entity: EntityT) -> None:
        """Add or update an entity on the platform."""
        # FUTURE: May need to support a compare function callback
        if address in self.addresses:
            if entity.detail != self.entities[address].detail:
                self.names[self.addresses.index(address)] = name
                self.entities[address].update_entity(name, entity.detail)
                self.status_events.notify(
                    f"{self.platform_name}.{EntityPlatformEvent.ENTITY_CHANGED}"
                )
            return

        self.entities[address] = entity
        self.addresses.append(address)
        self.names.append(name)
        self.status_events.notify(
            f"{self.platform_name}.{EntityPlatformEvent.ENTITY_ADDED}"
        )

    def __getitem__(self, key: str) -> EntityT | None:
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

    def get_by_id(self, key: str) -> EntityT | None:
        """Return entity given an address."""
        if key in self.addresses:
            return self.entities[key]
        return None

    def get_by_name(self, key: str) -> EntityT | None:
        """Return entity given a name."""
        if key in self.names:
            i = self.names.index(key)
            return self.entities[self.addresses[i]]
        return None

    def get_by_index(self, value: int) -> EntityT | None:
        """Return entity given an index."""
        if not (0 <= value <= len(self.addresses)):
            return None
        return list(self.entities.values())[value]

    def to_dict(self) -> dict:
        """Dump entity platform entities to dict."""
        return {
            str(entity): {
                "status": entity.status,
                "detail": entity.detail.__dict__,
            }
            for entity in self.values()
        }

    def get_children(self, address: str) -> set[EntityT]:
        """Return the children of the a given address."""
        return {e for e in self.values() if e.detail.parent == address}

    def get_tree(self, address: str | None = None) -> dict:
        """Return a tree representation of the entity platform."""
        if address is None:
            roots = {e for e in self.values() if not e.detail.parent}
        else:
            roots = {self.entities[address]}

        # traversal of the tree from top down
        def traverse(
            hierarchy: dict[str, dict], entities: Iterable[EntityT], path: str = ""
        ) -> dict[str, dict]:
            for i in entities:
                children = self.get_children(i.address)
                new_path = f"{path}/{i.name} ({i.address})"
                hierarchy[i.name] = asdict(
                    TreeLeaf(
                        protocol=i.protocol,
                        type_=type(i).__name__,
                        address=i.address,
                        children=traverse({}, children, new_path),
                        path=new_path,
                    )
                )
            return hierarchy

        return traverse({}, roots)

    def get_directory(self, address: str | None = None) -> dict:
        """Return a flat directory representation of the entity platform."""
        if address is None:
            roots = {e for e in self.values() if not e.detail.parent}
        else:
            roots = {self.entities[address]}

        directory: dict[str, EntityT] = {}

        # traversal of the tree from top down
        def traverse(
            hierarchy: dict[str, dict], entities: Iterable[EntityT], path: str = ""
        ) -> dict[str, dict]:
            for i in entities:
                new_path = f"{path}/{i.name} ({i.address})"
                directory[new_path] = i
                traverse({}, self.get_children(i.address), new_path)
            return hierarchy

        traverse({}, roots)
        return directory


@dataclass
class TreeLeaf:
    """Dataclass to hold tree information."""

    type_: str = ""
    protocol: EntityProtocol | None = None
    address: str = ""
    children: dict[str, dict] = field(default_factory=dict)
    path: str = ""


class EntityPlatformEvent(StrEnum):
    """Events for entity platform status updates."""

    ENTITY_ADDED = "entity_added"
    ENTITY_CHANGED = "entity_changed"
    ENTITY_REMOVED = "entity_removed"
