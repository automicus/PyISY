"""Tests for :mod:`pyisy.programs`."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pyisy.constants import TAG_FOLDER, TAG_PROGRAM
from pyisy.exceptions import ISYResponseParseError
from pyisy.programs import Programs


@pytest.fixture
def parsed_programs(programs_xml: str) -> Programs:
    return Programs(MagicMock(), xml=programs_xml)


def test_parse_populates_collections(parsed_programs: Programs) -> None:
    assert parsed_programs.addresses
    assert (
        len(parsed_programs.addresses)
        == len(parsed_programs.pnames)
        == len(parsed_programs.ptypes)
        == len(parsed_programs.pobjs)
        == len(parsed_programs.pparents)
    )


def test_parse_includes_folders_and_programs(parsed_programs: Programs) -> None:
    types = set(parsed_programs.ptypes)
    assert {TAG_FOLDER, TAG_PROGRAM} <= types


def test_address_format_is_zero_padded_hex(parsed_programs: Programs) -> None:
    # Program addresses are 4-char zero-padded ids ("0001", "009C", ...).
    assert all(len(a) == 4 for a in parsed_programs.addresses)


def test_invalid_xml_raises_parse_error() -> None:
    with pytest.raises(ISYResponseParseError):
        Programs(MagicMock(), xml="<bad")
