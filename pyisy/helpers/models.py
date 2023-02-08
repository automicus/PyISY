"""Dataclass and TypedDict models for PyISY."""
from __future__ import annotations

from contextlib import suppress
from dataclasses import InitVar, dataclass, field
from datetime import datetime
from typing import Any, Generic, TypeVar, cast

from pyisy.constants import DEFAULT_PRECISION, DEFAULT_UNIT_OF_MEASURE

NumT = int | float
OptionalIntT = int | None
StatusT = TypeVar("StatusT", str, bool, NumT, OptionalIntT, None)


EntityDetailT = TypeVar("EntityDetailT", bound="EntityDetail")


@dataclass
class EntityDetail:
    """Dataclass to hold entity detail info."""

    parent: str | dict[str, str] | None = None


@dataclass
class EntityStatus(Generic[StatusT, EntityDetailT]):
    """Dataclass representation of a status update."""

    address: str
    status: StatusT
    detail: EntityDetailT
    last_changed: datetime
    last_update: datetime


@dataclass
class EventData:
    """Dataclass to represent the event data returned from the stream."""

    seqnum: str = ""
    sid: str = ""
    control: str = ""
    action: dict[str, Any] | str | None = None
    node: str | None = None
    event_info: dict[str, Any] | str | None = None
    fmt_act: str | None = None
    fmt_name: str | None = None


@dataclass
class NodeChangedEvent:
    """Class representation of a node change event."""

    address: str
    action: str
    event_info: dict


@dataclass
class NodeNotes:
    """Dataclass for holding node notes information."""

    spoken: str = ""
    is_load: bool = False
    description: str = ""
    location: str = ""


@dataclass
class NodeProperty:
    """Class to hold result of a control event or node aux property."""

    id: InitVar[str | None] = ""
    control: str = ""
    value: OptionalIntT | float = None
    precision: int = DEFAULT_PRECISION
    uom: str = DEFAULT_UNIT_OF_MEASURE
    formatted: str = ""
    address: str | None = None

    # pylint: disable=redefined-builtin
    def __post_init__(self, id: str | None) -> None:
        """Post-process Node Property after initialization."""
        if id:
            self.control = id

        if self.value is not None and isinstance(cast(str, self.value), str):
            with suppress(ValueError):
                self.value = (
                    int(self.value) if cast(str, self.value).strip() != "" else None
                )


@dataclass
class ZWaveParameter:
    """Class to hold Z-Wave Parameter from a Z-Wave Node."""

    param_num: int
    size: int
    value: int | str

    def __post_init__(self) -> None:
        """Post-process a Z-Wave Parameter."""
        self.param_num = int(cast(str, self.param_num))
        self.size = int(cast(str, self.size))
        with suppress(ValueError):
            self.value = int(cast(str, self.value))


@dataclass
class ZWaveProperties:
    """Class to hold Z-Wave Product Details from a Z-Wave Node."""

    category: str = "0"
    mfg: str = "0.0.0"
    gen: str = "0.0.0"
    basic_type: str = field(init=False, default="0x0000")
    generic_type: str = field(init=False, default="0x0000")
    specific_type: str = field(init=False, default="0x0000")
    mfr_id: str = field(init=False, default="0x0000")
    prod_type_id: str = field(init=False, default="0x0000")
    product_id: str = field(init=False, default="0x0000")

    def __post_init__(self) -> None:
        """Post-initialize Z-Wave Properties dataclass."""
        if self.gen:
            (
                self.basic_type,
                self.generic_type,
                self.specific_type,
            ) = (f"{int(x):#0{6}x}" for x in self.gen.split("."))

        if self.mfg:
            (self.mfr_id, self.prod_type_id, self.product_id) = (
                f"{int(x):#0{6}x}" for x in self.mfg.split(".")
            )
