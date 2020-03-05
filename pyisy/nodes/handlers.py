"""Node Event Handler Classes."""


class EventEmitter:
    """Event Emitter class."""

    def __init__(self):
        """Initialize a new Event Emitter class."""
        self._subscribers = []

    def subscribe(self, callback):
        """Subscribe to the events."""
        listener = EventListener(self, callback)
        self._subscribers.append(listener)
        return listener

    def unsubscribe(self, listener):
        """Unsubscribe from the events."""
        self._subscribers.remove(listener)

    def notify(self, event):
        """Notify a listener."""
        for subscriber in self._subscribers:
            subscriber.callback(event)


class EventListener:
    """Event Listener class."""

    def __init__(self, emitter, callback):
        """Initialize a new Event Listener class."""
        self._emitter = emitter
        self.callback = callback

    def unsubscribe(self):
        """Unsubscribe from the events."""
        self._emitter.unsubscribe(self)


class EventResult(dict):
    """Class to hold result of a command event."""

    def __init__(self, event, nval=None, prec=None, uom=None, formatted=None):
        """Initialize an event result."""
        super().__init__(
            self, event=event, nval=nval, prec=prec, uom=uom, formatted=formatted
        )
        self._event = event
        self._nval = nval
        self._prec = prec
        self._uom = uom
        self._formatted = formatted

    @property
    def event(self):
        """Report the event control string."""
        return self._event

    @property
    def nval(self):
        """Report the value, if there was one."""
        return self._nval

    @property
    def prec(self):
        """Report the precision, if there was one."""
        return self._prec

    @property
    def uom(self):
        """Report the unit of measure, if there was one."""
        return self._uom

    @property
    def formatted(self):
        """Report the formatted value, if there was one."""
        return self._formatted

    def __str__(self):
        """Return just the event title to prevent breaking changes."""
        return str(self.event)

    __repr__ = __str__
