"""Manage variables from the ISY."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pyisy.constants import (
    ATTR_INIT,
    ATTR_SET,
    PROTO_INT_VAR,
    PROTO_STATE_VAR,
    URL_VARIABLES,
    VAR_INTEGER,
)
from pyisy.helpers import now
from pyisy.helpers.entity import Entity, EntityStatus
from pyisy.logging import _LOGGER


@dataclass
class VariableStatus(EntityStatus):
    """Dataclass to hold variable status."""

    init: int | float
    timestamp: datetime
    prec: str = "0"


class Variable(Entity):
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
        self._address = f"{vtype}.{vid}"
        self._name = vname
        self._protocol = PROTO_INT_VAR if vtype == VAR_INTEGER else PROTO_STATE_VAR
        self._var_id = vid
        self._var_type = vtype
        self._init = init
        self._last_edited = timestamp
        self._prec = prec
        self._status = status
        self._variables = variables
        self.isy = variables.isy

    def __str__(self):
        """Return a string representation of the variable."""
        return f"Variable(type={self._var_type}, id={self._var_id}, value={self.status}, init={self.init})"

    def __repr__(self):
        """Return a string representation of the variable."""
        return str(self)

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
    def last_edited(self):
        """Return the last edit time."""
        return self._last_edited

    def update_last_edited(self, timestamp: datetime) -> None:
        """Set the UTC Time of the last edited time for this node."""
        if self._last_edited != timestamp:
            self._last_edited = timestamp

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
    def status_feedback(self):
        """Return information for a status change event."""
        return VariableStatus(
            address=self.address,
            status=self.status,
            last_changed=self.last_changed,
            last_update=self.last_update,
            init=self._init,
            timestamp=self._last_edited,
            prec=self._prec,
        )

    @property
    def vid(self):
        """Return the Variable ID."""
        return self._var_id

    async def update(self, wait_time: float = 0):
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
                str(self._var_type),
                str(self._var_id),
                str(val),
            ]
        )
        if not await self.isy.conn.request(req_url):
            _LOGGER.warning(
                "ISY could not set variable%s: %s.%s",
                " init value" if init else "",
                str(self._var_type),
                str(self._var_id),
            )
            return
        _LOGGER.debug(
            "ISY set variable%s: %s.%s",
            " init value" if init else "",
            str(self._var_type),
            str(self._var_id),
        )
        if not self.isy.auto_update:
            await self.update()
