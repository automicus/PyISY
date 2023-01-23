"""Manage variables from the ISY."""
from __future__ import annotations

from dataclasses import InitVar, dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from pyisy.constants import ATTR_INIT, ATTR_SET, URL_VARIABLES, VAR_INTEGER, Protocol
from pyisy.helpers import convert_isy_raw_value
from pyisy.helpers.entity import Entity, EntityDetail, EntityStatus, NumT
from pyisy.helpers.events import EventEmitter
from pyisy.logging import _LOGGER

if TYPE_CHECKING:
    from pyisy.variables import Variables


@dataclass
class VariableStatus(EntityStatus):
    """Dataclass to hold variable status."""

    initial: NumT
    timestamp: datetime
    precision: int = 0


@dataclass
class VariableDetail(EntityDetail):
    """Dataclass to hold variable detail info."""

    init: InitVar[str] = "0"
    val: InitVar[str] = "0"
    id: str = ""
    name: str = ""
    type_: str = "1"
    ts: datetime = datetime.now()
    precision: int = 0
    value: NumT = field(init=False)
    initial: NumT = field(init=False)

    def __post_init__(
        self,
        init: str,
        val: str,
    ) -> None:
        """Post process the entity detailed info."""
        self.value = convert_isy_raw_value(int(val), "", self.precision)
        self.initial = convert_isy_raw_value(int(init), "", self.precision)


class Variable(Entity[VariableDetail, NumT]):
    """Object representing a variable on the controller."""

    _last_edited: datetime
    _initial: NumT
    _var_id: str
    _var_type: str
    _precision: int

    def __init__(
        self, platform: Variables, address: str, name: str, detail: VariableDetail
    ) -> None:
        """Initialize a Variable class."""
        self.status_events = EventEmitter()
        self.platform = platform
        self.isy = platform.isy
        self._last_update = datetime.now()
        self._address = address
        self._var_type = detail.type_
        if self._var_type == VAR_INTEGER:
            self._protocol = Protocol.INT_VAR
        else:
            self._protocol = Protocol.STATE_VAR
        self.update_entity(name, detail)

    def update_entity(self, name: str, detail: VariableDetail) -> None:
        """Update an entity information."""
        self._name = name
        self._last_edited = detail.ts
        self._precision = detail.precision
        self._status = detail.value
        self._initial = detail.initial
        self._var_id = detail.id
        self._var_type = detail.type_
        self.detail = detail
        self._last_changed = datetime.now()
        self.status_events.notify(self.status_feedback)

    @property
    def initial(self) -> NumT:
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

    async def set_initial(self, value: NumT) -> bool:
        """Set the initial value for the variable."""
        return await self.set_value(value, True)

    async def set_value(self, value: NumT, init: bool = False) -> bool:
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
                "Could not set variable %s %svalue to %s",
                self.address,
                "init " if init else "",
                value,
            )
            return False
        _LOGGER.debug(
            "Set variable %s %svalue to %s",
            self.address,
            "init " if init else "",
            value,
        )
        return True
