"""Manage variables from the ISY."""
from ..constants import (
    ATTR_INIT,
    ATTR_LAST_CHANGED,
    ATTR_LAST_UPDATE,
    ATTR_PRECISION,
    ATTR_SET,
    ATTR_STATUS,
    ATTR_TS,
    PROTO_INT_VAR,
    PROTO_STATE_VAR,
    TAG_ADDRESS,
    URL_VARIABLES,
    VAR_INTEGER,
)
from ..helpers import EventEmitter, now
from ..logging import _LOGGER


class Variable:
    """
    Object representing a variable on the controller.

    |  variables: The variable manager object.
    |  vid: List of variable IDs.
    |  vtype: List of variable types.
    |  init: List of values that variables initialize to when the controller
             starts.
    |  val: The current variable value.
    |  ts: The timestamp for the last time the variable was edited.

    :ivar init: Watched property that represents the value the variable
                initializes to when the controller boots.
    :ivar lastEdit: Watched property that indicates the last time the variable
                    was edited.
    :ivar val: Watched property that represents the value of the variable.
    """

    def __init__(self, variables, vid, vtype, vname, init, status, timestamp, prec):
        """Initialize a Variable class."""
        super().__init__()
        self._id = vid
        self._init = init
        self._last_edited = timestamp
        self._last_update = now()
        self._last_changed = now()
        self._name = vname
        self._prec = prec
        self._status = status
        self._type = vtype
        self._variables = variables
        self.isy = variables.isy
        self.status_events = EventEmitter()

    def __str__(self):
        """Return a string representation of the variable."""
        return f"Variable(type={self._type}, id={self._id}, value={self.status}, init={self.init})"

    def __repr__(self):
        """Return a string representation of the variable."""
        return str(self)

    @property
    def address(self):
        """Return the formatted Variable Type and ID."""
        return f"{self._type}.{self._id}"

    @property
    def init(self):
        """Return the initial state."""
        return self._init

    @init.setter
    def init(self, value):
        """Set the initial state and notify listeners."""
        if self._init != value:
            self._init = value
            self._last_changed = now()
            self.status_events.notify(self.status_feedback)
        return self._init

    @property
    def last_changed(self):
        """Return the UTC Time of the last status change for this node."""
        return self._last_changed

    @property
    def last_edited(self):
        """Return the last edit time."""
        return self._last_edited

    @last_edited.setter
    def last_edited(self, value):
        """Set the last edited time."""
        if self._last_edited != value:
            self._last_edited = value
        return self._last_edited

    @property
    def last_update(self):
        """Return the UTC Time of the last update for this node."""
        return self._last_update

    @last_update.setter
    def last_update(self, value):
        """Set the last update time."""
        if self._last_update != value:
            self._last_update = value
        return self._last_update

    @property
    def protocol(self):
        """Return the protocol for this entity."""
        return PROTO_INT_VAR if self._type == VAR_INTEGER else PROTO_STATE_VAR

    @property
    def name(self):
        """Return the Variable Name."""
        return self._name

    @property
    def prec(self):
        """Return the Variable Precision."""
        return self._prec

    @prec.setter
    def prec(self, value):
        """Set the current node state and notify listeners."""
        if self._prec != value:
            self._prec = value
            self._last_changed = now()
            self.status_events.notify(self.status_feedback)
        return self._prec

    @property
    def status(self):
        """Return the current node state."""
        return self._status

    @status.setter
    def status(self, value):
        """Set the current node state and notify listeners."""
        if self._status != value:
            self._status = value
            self._last_changed = now()
            self.status_events.notify(self.status_feedback)
        return self._status

    @property
    def status_feedback(self):
        """Return information for a status change event."""
        return {
            TAG_ADDRESS: self.address,
            ATTR_STATUS: self._status,
            ATTR_INIT: self._init,
            ATTR_PRECISION: self._prec,
            ATTR_TS: self._last_edited,
            ATTR_LAST_CHANGED: self._last_changed,
            ATTR_LAST_UPDATE: self._last_update,
        }

    @property
    def vid(self):
        """Return the Variable ID."""
        return self._id

    async def update(self, wait_time=0):
        """
        Update the object with the variable's parameters from the controller.

        |  wait_time: Seconds to wait before updating.
        """
        self._last_update = now()
        await self._variables.update(wait_time)

    async def set_init(self, val):
        """
        Set the initial value for the variable after the controller boots.

        |  val: The value to have the variable initialize to.
        """
        if val is None:
            raise ValueError("Variable init must be an integer. Got None.")
        self.set_value(val, True)

    async def set_value(self, val, init=False):
        """
        Set the value of the variable.

        |  val: The value to set the variable to.
        """
        if val is None:
            raise ValueError("Variable value must be an integer. Got None.")
        req_url = self.isy.conn.compile_url(
            [
                URL_VARIABLES,
                ATTR_INIT if init else ATTR_SET,
                str(self._type),
                str(self._id),
                str(val),
            ]
        )
        if not await self.isy.conn.request(req_url):
            _LOGGER.warning(
                "ISY could not set variable%s: %s.%s",
                " init value" if init else "",
                str(self._type),
                str(self._id),
            )
            return
        _LOGGER.debug(
            "ISY set variable%s: %s.%s",
            " init value" if init else "",
            str(self._type),
            str(self._id),
        )
        if not self.isy.auto_update:
            await self.update()
