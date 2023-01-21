"""Helper functions for the PyISY Module."""
from __future__ import annotations

from random import getrandbits
from typing import cast

from pyisy.constants import ISY_VALUE_UNKNOWN, UOM_DOUBLE_TEMP, UOM_ISYV4_DEGREES
from pyisy.helpers.xml import (
    attr_from_element,
    attr_from_xml,
    value_from_nested_xml,
    value_from_xml,
)

__all__ = [
    "value_from_xml",
    "attr_from_xml",
    "attr_from_element",
    "value_from_nested_xml",
    "random_uuid_hex",
    "convert_isy_raw_value",
]


def random_uuid_hex() -> str:
    """Generate a random UUID hex."""
    return "%032x" % getrandbits(32 * 4)


def convert_isy_raw_value(
    value: int | float,
    uom: str | None,
    precision: int | str,
    fallback_precision: int | None = None,
) -> float | int:
    """Fix ISY Reported Values.

    ISY provides float values as an integer and precision component.
    Correct by shifting the decimal place left by the value of precision.
    (e.g. value=2345, prec="2" == 23.45)

    Insteon Thermostats report temperature in 0.5-deg precision as an int
    by sending a value of 2 times the Temp. Correct by dividing by 2 here.
    """
    if value is None or value == ISY_VALUE_UNKNOWN:
        return ISY_VALUE_UNKNOWN
    if uom in (UOM_DOUBLE_TEMP, UOM_ISYV4_DEGREES):
        return round(float(value) / 2.0, 1)
    if precision not in ("0", 0):
        return cast(float, round(float(value) / 10 ** int(precision), int(precision)))
    if fallback_precision:
        return round(float(value), fallback_precision)
    return value