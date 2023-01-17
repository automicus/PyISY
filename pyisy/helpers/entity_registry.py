"""Registry to manage node entities in different platforms.

This has been adapted from home-assistant/core:
homeassistant.helpers.entity_registry
"""
from __future__ import annotations

from collections import UserDict
from collections.abc import ValuesView
from typing import TYPE_CHECKING, TypeVar

import attr

from pyisy.helpers import random_uuid_hex

if TYPE_CHECKING:
    from pyisy.isy import ISY

T = TypeVar("T")


@attr.s(slots=True, frozen=True)
class RegistryEntry:
    """Entity Registry Entry."""

    address: str = attr.ib()
    unique_id: str = attr.ib()
    platform: str = attr.ib()
    id: str = attr.ib(factory=random_uuid_hex)
    name: str | None = attr.ib(default=None)


class EntityRegistryItems(UserDict[str, "RegistryEntry"]):
    """Container for entity registry items, maps address -> entry.

    Maintains two additional indexes:
    - id -> entry
    - (platform, unique_id) -> address
    """

    def __init__(self) -> None:
        """Initialize the container."""
        super().__init__()
        self._entry_ids: dict[str, RegistryEntry] = {}
        self._index: dict[tuple[str, str], str] = {}

    def values(self) -> ValuesView[RegistryEntry]:
        """Return the underlying values to avoid __iter__ overhead."""
        return self.data.values()

    def __setitem__(self, key: str, entry: RegistryEntry) -> None:
        """Add an item."""
        if key in self:
            old_entry = self[key]
            del self._entry_ids[old_entry.id]
            del self._index[(old_entry.platform, old_entry.unique_id)]
        super().__setitem__(key, entry)
        self._entry_ids[entry.id] = entry
        self._index[(entry.platform, entry.unique_id)] = entry.address

    def __delitem__(self, key: str) -> None:
        """Remove an item."""
        entry = self[key]
        del self._entry_ids[entry.id]
        del self._index[(entry.platform, entry.unique_id)]
        super().__delitem__(key)

    def get_address(self, key: tuple[str, str]) -> str | None:
        """Get address from (platform, unique_id)."""
        return self._index.get(key)

    def get_entry(self, key: str) -> RegistryEntry | None:
        """Get entry from id."""
        return self._entry_ids.get(key)


class EntityRegistry:
    """Class to hold a registry of entities."""

    entities: EntityRegistryItems
    isy: ISY

    def __init__(self, isy: ISY) -> None:
        """Initialize the registry."""
        self.isy = isy
