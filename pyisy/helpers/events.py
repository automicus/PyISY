"""Event Handlers and Helpers."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, is_dataclass
from typing import TYPE_CHECKING, Any, TypeVar

from pyisy.logging import _LOGGER

if TYPE_CHECKING:
    from pyisy.helpers.entity import EntityStatus
    from pyisy.helpers.models import NodeProperty

_T = TypeVar("_T")

_CallableT = TypeVar("_CallableT", bound=Callable[..., Any])


class EventEmitter:
    """Event Emitter class."""

    _subscribers: list[EventListener]

    def __init__(self) -> None:
        """Initialize a new Event Emitter class."""
        self._subscribers = []

    def subscribe(
        self,
        callback: _CallableT,
        event_filter: dict | str | None = None,
        key: str | None = None,
    ) -> EventListener:
        """Subscribe to the events."""
        listener = EventListener(
            emitter=self, callback=callback, event_filter=event_filter, key=key
        )
        self._subscribers.append(listener)
        return listener

    def unsubscribe(self, listener: EventListener) -> None:
        """Unsubscribe from the events."""
        self._subscribers.remove(listener)

    def notify(
        self, event: EntityStatus | NodeProperty | NodeChangedEvent | str | None
    ) -> None:
        """Notify a listener."""
        for subscriber in self._subscribers:
            # Guard against downstream errors interrupting the socket connection (#249)
            try:
                if e_filter := subscriber.event_filter:
                    if is_dataclass(event) and isinstance(e_filter, dict):
                        if not (e_filter.items() <= event.__dict__.items()):
                            continue
                    elif event != e_filter:
                        continue

                if subscriber.key:
                    subscriber.callback(event, subscriber.key)
                    continue
                subscriber.callback(event)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Error during callback of %s", event)


@dataclass
class EventListener:
    """Event Listener class."""

    emitter: EventEmitter
    callback: Callable
    event_filter: dict | str | None
    key: str | None

    def unsubscribe(self) -> None:
        """Unsubscribe from the events."""
        self.emitter.unsubscribe(self)


@dataclass
class NodeChangedEvent:
    """Class representation of a node change event."""

    address: str
    action: str
    event_info: dict
