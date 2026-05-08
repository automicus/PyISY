"""Tests for the rest of the programs surface — folder/program property
getters and setters, ``Programs`` navigation/iteration, and the real
``Programs.update_received`` websocket event handler.
"""

from __future__ import annotations

from datetime import UTC, datetime
from xml.dom import minidom

import pytest

from pyisy.constants import (
    PROTO_FOLDER,
    PROTO_PROGRAM,
    TAG_FOLDER,
    TAG_PROGRAM,
)
from pyisy.isy import ISY

# -- helpers -----------------------------------------------------------


def _first_program(isy: ISY):
    for addr, ptype in zip(isy.programs.addresses, isy.programs.ptypes, strict=False):
        if ptype == TAG_PROGRAM:
            return isy.programs[addr].leaf
    pytest.fail("no programs in fixture")


def _first_folder(isy: ISY):
    for addr, ptype in zip(isy.programs.addresses, isy.programs.ptypes, strict=False):
        if ptype == TAG_FOLDER and addr != "0001":
            return isy.programs[addr].leaf
    pytest.fail("no program folders in fixture")


# -- Program / Folder property smoke ----------------------------------


def test_folder_str_repr_address(isy: ISY) -> None:
    folder = _first_folder(isy)
    assert str(folder).startswith("Folder(")
    assert folder.address == folder._id
    assert folder.protocol == PROTO_FOLDER
    assert isinstance(folder.name, str) and folder.name


def test_program_str_repr_address(isy: ISY) -> None:
    program = _first_program(isy)
    assert str(program).startswith("Program(")
    assert program.protocol == PROTO_PROGRAM
    assert isinstance(program.name, str) and program.name


def test_folder_status_feedback_shape(isy: ISY) -> None:
    folder = _first_folder(isy)
    fb = folder.status_feedback
    # Standard shape used by HA's program-platform polling code.
    assert "address" in fb
    assert "status" in fb


# -- Folder setters ---------------------------------------------------


def test_folder_last_changed_setter_only_writes_on_change(isy: ISY) -> None:
    folder = _first_folder(isy)
    ts = datetime(2026, 5, 2, 12, 0, 0, tzinfo=UTC)
    folder.last_changed = ts
    assert folder.last_changed == ts
    folder.last_changed = ts  # no-op path
    assert folder.last_changed == ts


def test_folder_last_update_setter_only_writes_on_change(isy: ISY) -> None:
    folder = _first_folder(isy)
    ts = datetime(2026, 5, 2, 12, 0, 0, tzinfo=UTC)
    folder.last_update = ts
    assert folder.last_update == ts
    folder.last_update = ts
    assert folder.last_update == ts


def test_folder_status_setter_fires_event_on_change(isy: ISY) -> None:
    folder = _first_folder(isy)
    seen: list = []
    folder.status_events.subscribe(seen.append)

    folder.status = 99
    # Folder.status setter notifies with the raw value (not status_feedback).
    assert seen == [99]
    folder.status = 99  # no-op path
    assert len(seen) == 1


# -- Program setters --------------------------------------------------


@pytest.mark.parametrize(
    "attr",
    ["enabled", "last_finished", "last_run", "ran_else", "ran_then", "run_at_startup", "running"],
)
def test_program_setters_only_write_on_change(isy: ISY, attr: str) -> None:
    """Each ``Program`` setter (enabled / last_finished / last_run /
    ran_else / ran_then / run_at_startup / running) writes only when the
    value actually changes — covers both branches of the no-op guard."""
    program = _first_program(isy)
    starting = getattr(program, attr)

    # Pick a value guaranteed to differ from the starting value.
    if isinstance(starting, bool) or starting in (True, False):
        new_value = not starting
    elif isinstance(starting, int):
        new_value = starting + 7
    elif isinstance(starting, datetime):
        new_value = (starting if starting else datetime(2020, 1, 1, tzinfo=UTC)).replace(year=2027)
    else:
        new_value = datetime(2027, 1, 1, tzinfo=UTC)

    setattr(program, attr, new_value)
    assert getattr(program, attr) == new_value
    setattr(program, attr, new_value)  # no-op
    assert getattr(program, attr) == new_value


def test_program_status_feedback_shape(isy: ISY) -> None:
    program = _first_program(isy)
    fb = program.status_feedback
    assert "address" in fb
    assert "status" in fb


# -- Programs.update_received (real websocket handler) ----------------


def _wrap_event(payload: str) -> minidom.Document:
    return minidom.parseString(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Event seqnum="1" sid="uuid:test"><control>_1</control>'
        f"<action>0</action><node></node><eventInfo>{payload}</eventInfo></Event>"
    )


def test_update_received_status_21_increments_ran_then(isy: ISY) -> None:
    program = _first_program(isy)
    starting = program.ran_then
    isy.programs.update_received(_wrap_event(f"<id>{program.address}</id><s>21</s>"))
    assert program.ran_then == starting + 1


def test_update_received_status_31_increments_ran_else(isy: ISY) -> None:
    program = _first_program(isy)
    starting = program.ran_else
    isy.programs.update_received(_wrap_event(f"<id>{program.address}</id><s>31</s>"))
    assert program.ran_else == starting + 1


def test_update_received_run_finish_timestamps(isy: ISY) -> None:
    """``<r>`` and ``<f>`` carry the last-run / last-finished timestamps;
    the captured router fixture has these fields."""
    program = _first_program(isy)
    isy.programs.update_received(
        _wrap_event(f"<id>{program.address}</id><r>260502 14:55:45 </r><f>260502 14:55:45 </f>")
    )
    assert program.last_run is not None
    assert program.last_finished is not None


def test_update_received_off_event_disables_program(isy: ISY) -> None:
    """An ``<off />`` element in the event payload flips ``enabled`` to
    False; ``<on />`` flips it back to True. Pre-#487 this branch was
    dead because ``minidom.toxml()`` strips the space and the substring
    check never matched."""
    program = _first_program(isy)
    program.enabled = True
    isy.programs.update_received(_wrap_event(f"<id>{program.address}</id><off /><nr />"))
    assert program.enabled is False
    isy.programs.update_received(_wrap_event(f"<id>{program.address}</id><on /><nr />"))
    assert program.enabled is True


def test_update_received_unknown_address_warns_and_ignores(isy: ISY, caplog) -> None:
    """A program update for an id we haven't loaded must log a warning
    and not crash — same pattern as the variables handler."""
    with caplog.at_level("WARNING", logger="pyisy"):
        isy.programs.update_received(_wrap_event("<id>FFFF</id><s>21</s>"))
    assert any("new program" in r.message.lower() for r in caplog.records)


def test_update_received_for_folder_target_is_no_op(isy: ISY) -> None:
    """``update_received`` short-circuits when the target is a Folder
    rather than a Program (folders don't track ran_then etc.)."""
    folder = _first_folder(isy)
    # Should not raise even though folder lacks ran_then/ran_else.
    isy.programs.update_received(_wrap_event(f"<id>{folder.address}</id><s>21</s>"))


# -- Programs manager: navigation, iteration, repr --------------------


def test_programs_str_at_root(isy: ISY) -> None:
    assert str(isy.programs) == "Folder <root>"


def test_programs_str_at_folder_navigates_into_subcontainer(isy: ISY) -> None:
    """Indexing a folder address returns a navigation-style ``Programs``
    sub-container — its ``__str__`` formats with a space before the id.
    Indexing a program address returns the leaf ``Program`` object
    directly, whose ``__str__`` has no space (``Program(008E)``)."""
    folder_addr = _first_folder(isy).address
    program_addr = _first_program(isy).address
    assert str(isy.programs[folder_addr]).startswith("Folder (")
    assert str(isy.programs[program_addr]).startswith("Program(")


def test_programs_repr_renders_tree(isy: ISY) -> None:
    """``repr`` walks the whole tree — exercises both folder-recursion
    and the leaf-program rendering branches."""
    out = repr(isy.programs)
    assert "Folder <root>" in out
    # At least one child folder should appear in the output.
    folder_name = _first_folder(isy).name
    assert folder_name in out


def test_programs_iter_yields_program_objects(isy: ISY) -> None:
    """``__iter__`` walks ``all_lower_programs`` (folders flattened
    away) and yields ``(path, Program)`` tuples. Drive a manual loop
    rather than ``list(iter(programs))`` — the underlying iterator
    class lacks ``__iter__`` returning self, so re-iterating with
    ``iter()`` raises TypeError. (Worth a separate cleanup PR.)"""
    from pyisy.programs.program import Program

    progs = []
    for path, obj in isy.programs:
        progs.append((path, obj))
    assert progs, "expected at least one program in fixture"
    assert all(isinstance(p, Program) for _, p in progs)


def test_programs_reversed_returns_iterator_in_opposite_order(isy: ISY) -> None:
    """``__reversed__`` returns a ``ProgramIterator`` started at the
    last index. Drive it manually with ``next()`` since the iterator
    class lacks ``__iter__`` returning self (so ``for x in
    reversed(programs)`` raises TypeError — separate cleanup)."""
    rev_it = reversed(isy.programs)
    backward = []
    while True:
        try:
            backward.append(next(rev_it))
        except StopIteration:
            break

    forward = list(isy.programs)
    assert backward == list(reversed(forward))


def test_programs_getitem_by_name_returns_match(isy: ISY) -> None:
    program = _first_program(isy)
    looked_up = isy.programs[program.name]
    # __getitem__ may resolve to either the leaf (Program) or the
    # navigation Programs wrapper depending on type — both have an
    # `address` matching the original.
    addr = looked_up.address if hasattr(looked_up, "address") else looked_up.root
    assert addr == program.address


def test_programs_getitem_unknown_returns_none(isy: ISY) -> None:
    """A string that can't be resolved as id, name, or int index
    returns ``None`` — consistent with the rest of the method's miss
    paths and the ``-> ... | None`` signature (PR #493)."""
    assert isy.programs["does-not-exist"] is None


def test_programs_setitem_is_silently_no_op(isy: ISY) -> None:
    """Programs container is read-only from the API — assignment is
    silently ignored."""
    isy.programs["anything"] = "value"
    # No state change beyond what was already loaded.
    assert isy.programs.addresses


def test_programs_get_by_name_walks_children(isy: ISY) -> None:
    program = _first_program(isy)
    found = isy.programs.get_by_name(program.name)
    # Only matches direct children of the current root; on the root
    # collection that means top-level entries. Verify the lookup path
    # runs without error and either returns a match or None.
    assert found is None or found.address == program.address


# -- name / all_lower_programs properties -----------------------------


def test_programs_name_at_root_is_empty(isy: ISY) -> None:
    assert isy.programs.name == ""


def test_programs_name_at_folder(isy: ISY) -> None:
    folder = _first_folder(isy)
    assert isy.programs[folder.address].name == folder.name


def test_all_lower_programs_returns_program_paths(isy: ISY) -> None:
    """``all_lower_programs`` recursively descends; every entry is a
    program (folders are flattened away). The path strings contain
    ``/`` separators when they cross a folder boundary."""
    paths = isy.programs.all_lower_programs
    assert paths
    for entry_type, _path, _ident in paths:
        assert entry_type == TAG_PROGRAM
