"""An abstract class for entities."""
from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, TypeVar

from pyisy.helpers.events import EventEmitter

# Typing imports that create a circular dependency
if TYPE_CHECKING:
    from pyisy.isy import ISY
    from pyisy.networking import NetworkResources
    from pyisy.nodes import Nodes
    from pyisy.programs import Programs
    from pyisy.variables import Variables


@dataclass
class EntityStatus:
    """Dataclass representation of a status update."""

    address: str
    status: int | float | None
    last_changed: datetime
    last_update: datetime


_EntityT = TypeVar("_EntityT", bound="Entity")


class Entity(ABC):
    """An abstract class for ISY entities.

    For consistency with downstream users of this module, every
    class for the different platforms inherits some essential properties
    from this class.

    Note: Adapted from home-assistant/core.
    """

    # SAFE TO OVERWRITE
    # The properties and methods here are safe to overwrite when inheriting
    # this class. These may be used to customize the behavior of the entity.
    _address: str = None  # type: ignore[assignment]

    # Owning isy instance. Will be set by platform
    # While not purely typed, it makes typehinting more useful for us
    # and removes the need for constant None checks or asserts.
    isy: ISY = None  # type: ignore[assignment]

    # Owning platform instance. Will be set by platform
    platform: Nodes | Programs | Variables | NetworkResources | None = None

    _enabled: bool = True
    _last_changed: datetime
    _last_update: datetime
    _name: str = ""
    _protocol: str | None = None
    _status: int | float | bool
    status_events: EventEmitter = EventEmitter()

    @property
    def address(self) -> str:
        """Return the entity ID."""
        return self._address

    @property
    def enabled(self):
        """Return if the entity is enabled on the controller."""
        return self._enabled

    @property
    def last_changed(self) -> datetime:
        """Return the UTC Time of the last status change for this entity."""
        return self._last_changed

    @property
    def last_update(self) -> datetime:
        """Return the UTC Time of the last update for this entity."""
        return self._last_update

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def protocol(self) -> str | None:
        """Return the protocol for this entity."""
        return self._protocol

    @property
    def status(self) -> int | float | bool:
        """Return the current entity state."""
        return self._status

    def update_enabled(self, value):
        """Set if the entity is enabled on the controller."""
        if self._enabled != value:
            self._enabled = value
        return self._enabled

    def update_status(self, value: int | float | bool) -> None:
        """Set the current entity state and notify listeners."""
        if self._status != value:
            self._status = value
            self._last_changed = datetime.now()
            self.status_events.notify(
                EntityStatus(
                    self.address, self.status, self._last_changed, self._last_update
                )
            )

    def update_last_changed(self, timestamp: datetime | None = None) -> None:
        """Set the UTC Time of the last status change for this entity."""
        if timestamp is None:
            timestamp = datetime.now()
        self._last_changed = timestamp

    def update_last_update(self, timestamp: datetime | None = None) -> None:
        """Set the UTC Time of the last update for this entity."""
        if timestamp is None:
            timestamp = datetime.now()
        self._last_update = timestamp

    def __str__(self) -> str:
        """Return a string representation of the entity."""
        return f"{type(self).__name__}({self.address})"
