"""Manage variables from the ISY."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from dateutil import parser

from pyisy.constants import (
    ATTR_INIT,
    ATTR_SET,
    PROTO_INT_VAR,
    PROTO_STATE_VAR,
    URL_VARIABLES,
    VAR_INTEGER,
)
from pyisy.helpers import convert_isy_raw_value, now
from pyisy.helpers.entity import Entity, EntityStatus
from pyisy.helpers.events import EventEmitter
from pyisy.logging import _LOGGER


@dataclass
class VariableStatus(EntityStatus):
    """Dataclass to hold variable status."""

    init: int | float
    timestamp: datetime
    prec: str = "0"


class Variable(Entity):
    """Object representing a variable on the controller."""

    _raw_value: int
    _raw_init_value: int
    _last_edited: datetime.datetime
    _var_id: str
    _var_type: str

    def __init__(self, platform, address, name, detail):
        """Initialize a Variable class."""
        self.status_events = EventEmitter()
        self.platform = platform
        self.isy = platform.isy
        self._last_update = now()
        self._address = address
        self._var_type = detail["@type"]
        if self._var_type == VAR_INTEGER:
            self._protocol = PROTO_INT_VAR
        else:
            self._protocol = PROTO_STATE_VAR
        self.update_entity(name, detail)

    def __str__(self):
        """Return a string representation of the variable."""
        return f"Variable(type={self._var_type}, id={self._var_id}, value={self.status}, init={self.init})"

    def __repr__(self):
        """Return a string representation of the variable."""
        return str(self)

    def update_entity(self, name: str, detail: dict) -> None:
        """Update an entity information."""
        self._last_edited = parser.parse(detail["ts"])
        self._name = name
        self._precision = detail["prec"]
        self._raw_value = int(detail["val"])
        self._status = convert_isy_raw_value(self._raw_value, "", self._precision)
        self._raw_init_value = detail["init"]
        self._init = convert_isy_raw_value(self._raw_init_value, "", self._precision)
        self._var_id = detail["@id"]
        self._var_type = detail["@type"]
        self.detail = detail
        self._last_changed = now()
        self.status_events.notify(self.status_feedback)

    @property
    def init(self):
        """Return the initial state."""
        return self._init

    @property
    def last_edited(self):
        """Return the last edit time."""
        return self._last_edited

    @property
    def prec(self):
        """Return the Variable Precision."""
        return self._precision

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
            prec=self._precision,
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
        await self.platform.update(wait_time)

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
