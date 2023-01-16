"""Helper functions for the PyISY Module."""
from __future__ import annotations

import datetime

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
]


def now() -> datetime.datetime:
    """Get the current system time."""
    return datetime.datetime.now()
