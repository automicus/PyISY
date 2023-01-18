"""Manage variables from the ISY."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from pyisy.variables import Variables


@dataclass
class VariableStatus(EntityStatus):
    """Dataclass to hold variable status."""

    initial: int | float
    timestamp: datetime
    precision: int = 0


class Variable(Entity):
    """Object representing a variable on the controller."""

    _raw_value: int
    _raw_init_value: int
    _last_edited: datetime
    _var_id: str
    _var_type: str
    _precision: int

    def __init__(
        self, platform: Variables, address: str, name: str, detail: dict
    ) -> None:
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

    def update_entity(self, name: str, detail: dict) -> None:
        """Update an entity information."""
        self._last_edited = parser.parse(detail["ts"])
        self._name = name
        self._precision = int(detail["prec"])
        self._raw_value = int(detail["val"])
        self._status = convert_isy_raw_value(self._raw_value, "", self._precision)
        self._raw_init_value = int(detail["init"])
        self._initial = convert_isy_raw_value(self._raw_init_value, "", self._precision)
        self._var_id = detail["@id"]
        self._var_type = detail["@type"]
        self.detail = detail
        self._last_changed = now()
        self.status_events.notify(self.status_feedback)

    @property
    def initial(self) -> int | float:
        """Return the initial state."""
        return self._initial

    @property
    def last_edited(self) -> datetime:
        """Return the last edit time."""
        return self._last_edited

    @property
    def precision(self) -> int:
        """Return the Variable Precision."""
        return self._precision

    @property
    def status_feedback(self) -> VariableStatus:
        """Return information for a status change event."""
        return VariableStatus(
            address=self.address,
            status=self.status,
            last_changed=self.last_changed,
            last_update=self.last_update,
            initial=self._initial,
            timestamp=self._last_edited,
            precision=self._precision,
        )

    @property
    def variable_id(self) -> str:
        """Return the Variable ID."""
        return self._var_id

    async def set_initial(self, value: int | float) -> bool:
        """Set the initial value for the variable."""
        return await self.set_value(value, True)

    async def set_value(self, value: int | float, init: bool = False) -> bool:
        """Set the value of the variable.

        ISY Version 5 firmware will automatically convert float back to int.
        """
        req_url = self.isy.conn.compile_url(
            [
                URL_VARIABLES,
                ATTR_INIT if init else ATTR_SET,
                self._var_type,
                self._var_id,
                str(value),
            ]
        )
        if not await self.isy.conn.request(req_url):
            _LOGGER.warning(
                "ISY could not set variable%s: %s.%s",
                " init value" if init else "",
                self._var_type,
                self._var_id,
            )
            return False
        _LOGGER.debug(
            "ISY set variable%s: %s.%s",
            " init value" if init else "",
            self._var_type,
            self._var_id,
        )
        return True
