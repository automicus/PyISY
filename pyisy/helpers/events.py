"""Event Handlers and Helpers."""
from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Generic, TypeVar

from pyisy.helpers.models import EntityStatus, EventData, NodeChangedEvent, NodeProperty
from pyisy.logging import _LOGGER

ATTR_EVENT_INFO = "event_info"

_T = TypeVar("_T")
_KeyT = TypeVar("_KeyT", bound=Hashable)
_EventT = NodeProperty | NodeChangedEvent | EntityStatus | EventData
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
        key: _KeyT | None = None,
    ) -> EventListener:
        """Subscribe to the EventEmitter's events.

        Args:
            callback (_CallableT):
                A callback function to call when an event is fired.
            event_filter (dict or str, optional):
                A filter string or dict to filter what events raise the callback.
                Defaults to None.
            key (_KeyT, optional):
                A key which, if provided, will be passed back to the callback.
                Defaults to None.

        Returns:
            EventListener:
                The EventListener object reference.
        """
        listener = EventListener(
            emitter=self, callback=callback, event_filter=event_filter, key=key
        )
        self._subscribers.append(listener)
        return listener

    def unsubscribe(self, listener: EventListener) -> None:
        """Unsubscribe from the events.

        Args:
            listener (EventListener):
                The listener object reference returned when subscribed.
        """
        self._subscribers.remove(listener)

    def notify(self, event: _EventT | str | None) -> None:
        """Notify all subscribed listeners.

        Args:
            event (_EventT):
                The event to pass on to the subscribed listeners.
        """
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
        event: _EventT,
    ) -> bool:
        """Evaluate a listener filter.

        Args:
            subscriber (EventListener):
                The subscriber for which to evaluate the filter.
            evt_filter (dict[str, str | dict[str, str]]):
                The event filter to test against the fired event.
            event (_EventT):
                The event against which the filter is evaluated.

        Returns:
            bool:
                If the event matches against the filter.
        """
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
class EventListener(Generic[_KeyT]):
    """Event Listener class."""

    emitter: EventEmitter
    callback: Callable
    event_filter: dict | str | None
    key: _KeyT | None

    def unsubscribe(self) -> None:
        """Unsubscribe from the event listener."""
        self.emitter.unsubscribe(self)
