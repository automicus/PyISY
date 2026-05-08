"""Tests for ``Folder`` / ``Program`` action methods called by HA."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from pyisy.constants import TAG_FOLDER, TAG_PROGRAM
from pyisy.isy import ISY
from pyisy.programs.program import Program


@pytest.fixture
def first_program(isy: ISY) -> Program:
    for addr, ptype in zip(isy.programs.addresses, isy.programs.ptypes, strict=False):
        if ptype == TAG_PROGRAM:
            return isy.programs[addr].leaf
    pytest.fail("no programs found in fixture")


@pytest.fixture
def first_folder(isy: ISY):
    # Skip the synthetic "0001" root; pick a real user folder if present.
    for addr, ptype in zip(isy.programs.addresses, isy.programs.ptypes, strict=False):
        if ptype == TAG_FOLDER and addr != "0001":
            return isy.programs[addr].leaf
    pytest.fail("no folders found in fixture")


@pytest.fixture
def request_mock(isy: ISY) -> AsyncMock:
    mock = AsyncMock(return_value="<x/>")
    isy.conn.request = mock  # type: ignore[assignment]
    # send_cmd calls update() on success when auto_update is False; suppress
    # that follow-up by stubbing get_programs too.
    isy.conn.get_programs = AsyncMock(return_value=None)  # type: ignore[assignment]
    return mock


def _called_url(mock: AsyncMock) -> str:
    return mock.await_args.args[0]


@pytest.mark.parametrize(
    ("method", "expected_cmd"),
    [
        ("run", "run"),
        ("run_then", "runThen"),
        ("run_else", "runElse"),
        ("stop", "stop"),
        ("enable", "enable"),
        ("disable", "disable"),
    ],
)
async def test_program_commands_hit_expected_url(
    first_program: Program,
    request_mock: AsyncMock,
    method: str,
    expected_cmd: str,
) -> None:
    result = await getattr(first_program, method)()
    assert result is True
    url = _called_url(request_mock)
    assert f"/programs/{first_program.address}/{expected_cmd}" in url


@pytest.mark.parametrize(
    ("method", "expected_cmd"),
    [
        ("enable_run_at_startup", "enableRunAtStartup"),
        ("disable_run_at_startup", "disableRunAtStartup"),
    ],
)
async def test_program_run_at_startup_commands(
    first_program: Program,
    request_mock: AsyncMock,
    method: str,
    expected_cmd: str,
) -> None:
    assert await getattr(first_program, method)() is True
    assert f"/{expected_cmd}" in _called_url(request_mock)


@pytest.mark.parametrize(
    ("method", "expected_cmd"),
    [("run", "run"), ("stop", "stop"), ("enable", "enable")],
)
async def test_folder_commands_hit_expected_url(
    first_folder, request_mock: AsyncMock, method: str, expected_cmd: str
) -> None:
    assert await getattr(first_folder, method)() is True
    assert f"/{expected_cmd}" in _called_url(request_mock)


async def test_program_command_returns_false_on_failure(
    first_program: Program, request_mock: AsyncMock
) -> None:
    request_mock.return_value = None
    assert await first_program.run() is False
