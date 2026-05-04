"""Tests for the rest of the variables surface — property getters and
setters, ``set_value`` / ``set_init`` (the write commands HA's variable
platform calls), and the real ``update_received`` websocket event
handler (the router-level test only verified dispatch, not that the
handler itself parses the payload correctly).
"""

from __future__ import annotations

from datetime import UTC
from unittest.mock import AsyncMock, MagicMock
from xml.dom import minidom

import pytest

from pyisy.constants import PROTO_INT_VAR, PROTO_STATE_VAR
from pyisy.isy import ISY
from pyisy.variables import Variables

# -- Variable: properties + setters ------------------------------------


def test_variable_str_and_repr_round_trip(isy: ISY) -> None:
    var = isy.variables[1][1]
    s = str(var)
    assert s.startswith("Variable(")
    assert "type=1" in s and "id=1" in s
    # __repr__ delegates to __str__.
    assert repr(var) == s


def test_variable_address(isy: ISY) -> None:
    int_var = isy.variables[1][1]  # Int_1
    state_var = isy.variables[2][1]  # first state var
    assert int_var.address == "1.1"
    assert state_var.address == "2.1"


def test_variable_protocol_distinguishes_int_and_state(isy: ISY) -> None:
    """``Variable.protocol`` returns ``PROTO_INT_VAR`` for type-1
    variables and ``PROTO_STATE_VAR`` for type-2. Pre-#485 the
    comparison was an int-vs-str mismatch and every variable reported
    as a state variable."""
    assert isy.variables[1][1].protocol == PROTO_INT_VAR
    assert isy.variables[2][1].protocol == PROTO_STATE_VAR


def test_variable_name_and_vid(isy: ISY) -> None:
    var = isy.variables[1][1]
    assert var.name == "Int_1"
    assert var.vid == 1


def test_variables_getitem_by_name_returns_variable(isy: ISY) -> None:
    """Within a type bucket, indexing by name returns the variable
    (regression for #486 — was a TypeError because the lookup tried to
    unpack a dict's keys)."""
    var = isy.variables[1]["Int_1"]
    assert var.vid == 1
    assert var.name == "Int_1"


def test_variables_getitem_unknown_name_raises_keyerror(isy: ISY) -> None:
    with pytest.raises(KeyError):
        _ = isy.variables[1]["does-not-exist"]


def test_variables_get_by_name_returns_first_match(isy: ISY) -> None:
    """``Variables.get_by_name`` walks ``children`` and returns the
    first ``(vtype, name, vid)`` whose name matches exactly. Pre-#486
    it used substring-against-tuple-repr, so partial matches could
    return the wrong variable."""
    var = isy.variables.get_by_name("Int_1")
    assert var is not None
    assert var.vid == 1
    assert var.protocol == PROTO_INT_VAR


def test_variables_get_by_name_unknown_returns_none(isy: ISY) -> None:
    assert isy.variables.get_by_name("does-not-exist") is None


@pytest.mark.parametrize(
    ("attr", "new_value"),
    [
        ("init", "42"),
        ("prec", 3),
        ("status", "99"),
    ],
)
def test_variable_setters_fire_status_events_on_change(isy: ISY, attr: str, new_value) -> None:
    """``init``, ``prec``, ``status`` setters notify ``status_events``
    only when the new value differs."""
    var = isy.variables[1][1]
    seen: list = []
    var.status_events.subscribe(seen.append)

    setattr(var, attr, new_value)
    assert len(seen) == 1, f"{attr} setter should have notified once"

    # Setting the same value again is a no-op.
    setattr(var, attr, new_value)
    assert len(seen) == 1, f"{attr} setter should not re-notify on no-op set"


def test_variable_last_changed_getter(isy: ISY) -> None:
    """``last_changed`` reflects the most recent setter that produced a
    real value change — fired by ``init``/``prec``/``status`` setters."""
    from datetime import datetime

    var = isy.variables[1][1]
    before = var.last_changed
    var.status = "777"  # forces _last_changed = now()
    assert var.last_changed > before
    assert isinstance(var.last_changed, datetime)


def test_variable_last_edited_setter_only_writes_on_change(isy: ISY) -> None:
    from datetime import datetime

    var = isy.variables[1][1]
    ts = datetime(2026, 5, 2, 12, 0, 0, tzinfo=UTC)
    var.last_edited = ts
    assert var.last_edited == ts
    # No-op setter path.
    var.last_edited = ts
    assert var.last_edited == ts


def test_variable_last_update_setter_only_writes_on_change(isy: ISY) -> None:
    from datetime import datetime

    var = isy.variables[1][1]
    ts = datetime(2026, 5, 2, 12, 0, 0, tzinfo=UTC)
    var.last_update = ts
    assert var.last_update == ts
    var.last_update = ts  # no-op
    assert var.last_update == ts


# -- Variable: set_value / set_init (the write commands) ---------------


async def test_variable_set_value_hits_set_url(isy: ISY) -> None:
    isy.conn.request = AsyncMock(return_value="<x/>")
    var = isy.variables[1][1]
    assert await var.set_value(42) is True
    url = isy.conn.request.await_args.args[0]
    # /rest/vars/set/<type>/<id>/<value>
    assert "/vars/set/1/1/42" in url


async def test_variable_set_init_hits_init_url(isy: ISY) -> None:
    """``set_init`` flips the path verb from ``set`` to ``init`` so the
    controller stores the value as the post-reboot initial value."""
    isy.conn.request = AsyncMock(return_value="<x/>")
    var = isy.variables[1][1]
    assert await var.set_init(7) is True
    url = isy.conn.request.await_args.args[0]
    assert "/vars/init/1/1/7" in url


async def test_variable_set_value_returns_false_on_failure(isy: ISY) -> None:
    isy.conn.request = AsyncMock(return_value=None)
    var = isy.variables[1][1]
    assert await var.set_value(42) is False


# -- Variables.update_received (real event dispatch) ------------------


def test_update_received_value_event_updates_status(isy: ISY) -> None:
    """``_1`` action=6 — value change. The router test only verified
    dispatch with a mock; this drives the real handler and confirms the
    target ``Variable``'s ``status``/``prec``/``last_edited`` move."""
    var = isy.variables[1][1]
    var.status = "0"  # known starting value

    event = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Event seqnum="1" sid="uuid:test"><control>_1</control>'
        '<action>6</action><node></node><eventInfo><var type="1" id="1">'
        "<prec>1</prec><val>20</val><ts>20260502 14:56:16</ts></var>"
        "</eventInfo></Event>"
    )
    isy.variables.update_received(minidom.parseString(event))
    assert var.status == 20
    assert var.prec == 1


def test_update_received_init_event_updates_init_value(isy: ISY) -> None:
    """``_1`` action=7 — init change. Touches the ``<init>`` branch
    inside ``update_received`` (different from the value branch)."""
    var = isy.variables[1][1]
    event = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Event seqnum="2" sid="uuid:test"><control>_1</control>'
        '<action>7</action><node></node><eventInfo><var type="1" id="1">'
        "<init>5</init><prec>1</prec></var></eventInfo></Event>"
    )
    isy.variables.update_received(minidom.parseString(event))
    assert var.init == 5


def test_update_received_unknown_variable_is_silently_ignored(isy: ISY) -> None:
    """A variable that hasn't been loaded yet (e.g. just created on the
    controller) shows up in events first; the handler must ignore it
    rather than crash."""
    event = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Event seqnum="3" sid="uuid:test"><control>_1</control>'
        '<action>6</action><node></node><eventInfo><var type="1" id="999">'
        "<prec>0</prec><val>0</val><ts>20260502 14:56:16</ts></var>"
        "</eventInfo></Event>"
    )
    # Should not raise.
    isy.variables.update_received(minidom.parseString(event))


# -- Variables manager: navigation, repr, lookup ----------------------


def test_variables_str_at_root_and_at_type(isy: ISY) -> None:
    assert str(isy.variables) == "Variable Collection"
    assert str(isy.variables[1]) == "Variable Collection (Type: 1)"


def test_variables_repr_at_root_dumps_both_types(isy: ISY) -> None:
    """``repr(variables)`` at root prints both type-1 and type-2
    sub-collections back-to-back."""
    r = repr(isy.variables)
    # Each sub-collection contributes its own header.
    assert r.count("Variable Collection (Type:") == 2
    assert "Int_1" in r


def test_variables_repr_at_type_lists_children(isy: ISY) -> None:
    r = repr(isy.variables[1])
    assert "Variable Collection (Type: 1)" in r
    assert "Int_1" in r


def test_variables_children_at_root_combines_both_types(isy: ISY) -> None:
    children = isy.variables.children
    types = {t for t, _name, _vid in children}
    assert types == {1, 2}


def test_variables_setitem_is_silently_no_op(isy: ISY) -> None:
    """Variables doesn't support assignment — the setter exists only to
    satisfy dict-like protocol expectations and returns silently."""
    isy.variables[1] = "anything"
    # No error, no state change.
    assert isy.variables[1].root == 1


def test_variables_unknown_var_id_raises_keyerror(isy: ISY) -> None:
    with pytest.raises(KeyError):
        _ = isy.variables[1][9999]


# -- Empty-variables corner cases (uncovered branches in __init__) ----


def test_variables_init_with_only_unparseable_definitions_warns(caplog) -> None:
    """If neither type's definitions parse successfully, the ctor
    short-circuits before trying to parse values — and logs a warning
    so the user knows the controller's variable feature didn't load."""
    isy = MagicMock()
    with caplog.at_level("WARNING", logger="pyisy"):
        Variables(isy, def_xml=None, var_xml=None)
    assert any("variables" in r.message.lower() for r in caplog.records)
