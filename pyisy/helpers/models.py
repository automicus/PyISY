"""Dataclass and TypedDict models for PyISY."""
from __future__ import annotations

from dataclasses import dataclass
from xml.dom import minidom

from pyisy.constants import (
    DEFAULT_PRECISION,
    DEFAULT_UNIT_OF_MEASURE,
    ISY_VALUE_UNKNOWN,
    TAG_CATEGORY,
    TAG_GENERIC,
    TAG_MFG,
)
from pyisy.helpers.xml import value_from_xml


@dataclass
class NodeProperty:
    """Class to hold result of a control event or node aux property."""

    control: str
    value: int | float = ISY_VALUE_UNKNOWN
    prec: str = DEFAULT_PRECISION
    uom: str | list[str] = DEFAULT_UNIT_OF_MEASURE
    formatted: str = ""
    address: str | None = None


@dataclass
class NodeNotes:
    """Dataclass for holding node notes information."""

    spoken: str = ""
    is_load: bool = False
    description: str = ""
    location: str = ""


@dataclass
class ZWaveProperties:
    """Class to hold Z-Wave Product Details from a Z-Wave Node."""

    category: str = "0"
    devtype_mfg: str = "0.0.0"
    devtype_gen: str = "0.0.0"
    basic_type: str = "0"
    generic_type: str = "0"
    specific_type: str = "0"
    mfr_id: str = "0"
    prod_type_id: str = "0"
    product_id: str = "0"
    raw: str = ""

    @classmethod
    def from_xml(cls, xml: minidom.Element) -> ZWaveProperties:
        """Return a Z-Wave Properties class from an xml DOM object."""
        category = value_from_xml(xml, TAG_CATEGORY)
        devtype_mfg = value_from_xml(xml, TAG_MFG)
        devtype_gen = value_from_xml(xml, TAG_GENERIC)
        raw = xml.toxml()
        basic_type = "0"
        generic_type = "0"
        specific_type = "0"
        mfr_id = "0"
        prod_type_id = "0"
        product_id = "0"
        if devtype_gen:
            (basic_type, generic_type, specific_type) = devtype_gen.split(".")
        if devtype_mfg:
            (mfr_id, prod_type_id, product_id) = devtype_mfg.split(".")

        return ZWaveProperties(
            category=category,
            devtype_mfg=devtype_mfg,
            devtype_gen=devtype_gen,
            basic_type=basic_type,
            generic_type=generic_type,
            specific_type=specific_type,
            mfr_id=mfr_id,
            prod_type_id=prod_type_id,
            product_id=product_id,
            raw=raw,
        )
