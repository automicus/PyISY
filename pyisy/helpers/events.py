"""Event Handlers and Helpers."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, is_dataclass
from typing import TYPE_CHECKING, Any, TypeVar

from pyisy.logging import _LOGGER

if TYPE_CHECKING:
    from pyisy.helpers.entity import EntityStatus
    from pyisy.helpers.models import NodeProperty

ATTR_EVENT_INFO = "event_info"

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
        """Notify all subscribed listeners."""
        for subscriber in self._subscribers:
            # Guard against downstream errors interrupting the socket connection (#249)
            try:
                if event is None:
                    subscriber.callback(None)
                    continue
                if evt_filter := subscriber.event_filter:
                    if isinstance(event, str):
                        if event != evt_filter:
                            continue
                    elif (
                        is_dataclass(event)
                        and isinstance(evt_filter, dict)
                        and not self.evaluate_filter(subscriber, evt_filter, event)
                    ):
                        continue

                if subscriber.key:
                    subscriber.callback(event, subscriber.key)
                    continue
                subscriber.callback(event)

            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Error during callback of %s", event)

    def evaluate_filter(
        self,
        subscriber: EventListener,
        evt_filter: dict[str, str | dict[str, str]],
        event: EntityStatus | NodeProperty | NodeChangedEvent,
    ) -> bool:
        """Evaluate a listener filter."""
        if isinstance(event, NodeChangedEvent) and ATTR_EVENT_INFO in evt_filter:
            # NodeChangedEvents can have a nested dict in the filter
            if not (
                isinstance((info_filter := evt_filter.get(ATTR_EVENT_INFO)), dict)
                and event.event_info is not None
                and info_filter.items() <= event.event_info.items()
            ):
                return False
            del evt_filter[ATTR_EVENT_INFO]
        if not (evt_filter.items() <= asdict(event).items()):
            return False
        return True


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
