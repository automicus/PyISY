"""Tests for :mod:`pyisy.variables`."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pyisy.variables import Variables


def test_parse_definitions_then_values(var_defs_xml: list[str], var_values_xml: str) -> None:
    isy = MagicMock()
    variables = Variables(isy, def_xml=var_defs_xml, var_xml=var_values_xml)

    # Type 1 (integer) and type 2 (state) both populated from the eisy export.
    assert variables.vids[1] == [1]
    assert variables.vnames[1][1] == "Int_1"
    assert variables.vids[2], "expected at least one state variable"

    # Values from the synthesized vars/get fixture should be reflected.
    int_var = variables[1][1]
    # status is stored as the raw string read from XML.
    assert int_var.status == "5"

    # State variable id=23 was given val=1 in the synthesized fixture.
    assert variables[2][23].status == "1"


def test_parse_definitions_handles_empty_response() -> None:
    """The connection layer can return ``"/CONF/INTEGER.VAR not found"`` when
    no integer variables are defined; that should leave the manager empty
    rather than raising."""
    isy = MagicMock()
    empty_defs = ["/CONF/INTEGER.VAR not found", "/CONF/STATE.VAR not found"]
    variables = Variables(isy, def_xml=empty_defs, var_xml=None)
    assert variables.vids == {1: [], 2: []}


def test_navigation_by_type(var_defs_xml: list[str], var_values_xml: str) -> None:
    variables = Variables(MagicMock(), def_xml=var_defs_xml, var_xml=var_values_xml)
    type1 = variables[1]
    assert type1.root == 1
    assert type1[1].vid == 1


def test_parse_values_with_bad_xml_raises(
    var_defs_xml: list[str],
) -> None:
    from pyisy.exceptions import ISYResponseParseError

    with pytest.raises(ISYResponseParseError):
        Variables(MagicMock(), def_xml=var_defs_xml, var_xml="<not-vars")


def test_parse_definitions_skips_bad_xml(caplog) -> None:
    """A malformed definitions response should log an error and continue,
    not raise — so a transient bad response on one type doesn't kill init."""
    isy = MagicMock()
    with caplog.at_level("ERROR", logger="pyisy"):
        variables = Variables(
            isy,
            def_xml=["<bad", '<CList type="VAR_INT"></CList>'],
            var_xml=None,
        )
    assert variables.vids == {1: [], 2: []}


def test_unknown_type_raises_keyerror(var_defs_xml: list[str], var_values_xml: str) -> None:
    variables = Variables(MagicMock(), def_xml=var_defs_xml, var_xml=var_values_xml)
    with pytest.raises(KeyError):
        _ = variables[3]
