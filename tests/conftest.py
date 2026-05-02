"""Shared fixtures for the PyISY test suite.

The suite is offline: a `FakeConnection` replaces the real aiohttp-backed
``Connection`` and serves canned XML captured from a real eisy in
``tests/fixtures/``. Tests that exercise parsing and lifecycle paths can
therefore run without any network access.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import quote, urlencode

import pytest

from pyisy.isy import ISY

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> str:
    """Return the contents of a fixture file under ``tests/fixtures``."""
    return (FIXTURES / name).read_text(encoding="utf-8")


def load_events(name: str = "websocket_events.log") -> list[str]:
    """Return one ``<?xml ...><Event>...</Event>`` string per line of the
    captured websocket log fixture. Useful for replaying real wire-format
    events through ``WebSocketClient._route_message``."""
    text = (FIXTURES / name).read_text(encoding="utf-8")
    return [line for line in text.splitlines() if line.strip()]


class FakeConnection:
    """Minimal stand-in for :class:`pyisy.connection.Connection`.

    Each ``get_*`` returns a canned string (or list, for variable defs). The
    instance also tracks attribute access so tests can assert which calls were
    made during ``ISY.initialize()``.
    """

    def __init__(
        self,
        config: str,
        nodes: str,
        status: str,
        programs: str,
        time: str,
        var_defs: Iterable[str],
        var_values: str,
        network: str | None = None,
    ) -> None:
        self.config = config
        self.nodes = nodes
        self.status = status
        self.programs = programs
        self.time = time
        self.var_defs = list(var_defs)
        self.var_values = var_values
        self.network = network

        self.increase_available_connections = MagicMock()
        self.close = AsyncMock()
        self.request = AsyncMock(return_value=None)
        self._url = "http://fake"
        self.connection_info: dict[str, Any] = {
            "auth": b"Basic dTpw",
            "addr": "127.0.0.1",
            "port": 80,
            "passwd": "p",
            "webroot": "",
        }

    async def test_connection(self) -> str:
        return self.config

    async def get_status(self) -> str:
        return self.status

    async def get_time(self) -> str:
        return self.time

    async def get_nodes(self) -> str:
        return self.nodes

    async def get_programs(self) -> str:
        return self.programs

    async def get_variable_defs(self) -> list[str]:
        return self.var_defs

    async def get_variables(self) -> str:
        return self.var_values

    async def get_network(self) -> str | None:
        return self.network

    def compile_url(self, path, query=None):
        url = self._url
        if path is not None:
            url += "/rest/" + "/".join(quote(item) for item in path)
        if query is not None:
            url += "?" + urlencode(query)
        return url


@pytest.fixture
def fixture_loader():
    """Expose ``load_fixture`` to tests."""
    return load_fixture


@pytest.fixture
def config_xml() -> str:
    return load_fixture("config.xml")


@pytest.fixture
def nodes_xml() -> str:
    return load_fixture("nodes.xml")


@pytest.fixture
def status_xml() -> str:
    return load_fixture("status.xml")


@pytest.fixture
def programs_xml() -> str:
    return load_fixture("programs.xml")


@pytest.fixture
def time_xml() -> str:
    return load_fixture("time.xml")


@pytest.fixture
def var_defs_xml() -> list[str]:
    return [load_fixture("vars_1.xml"), load_fixture("vars_2.xml")]


@pytest.fixture
def var_values_xml() -> str:
    """Concatenated /vars/get/1 + /vars/get/2 response, as ``Connection.get_variables``
    returns it: a single ``<vars>...</vars>`` document with the inner
    boundary collapsed."""
    a = load_fixture("vars_get_1.xml").strip()
    b = load_fixture("vars_get_2.xml").strip()
    # Drop the closing of (a) and opening of (b) so the merged string is valid XML.
    assert a.endswith("</vars>") and b.startswith("<vars>")
    return a[: -len("</vars>")] + b[len("<vars>") :]


@pytest.fixture
def fake_connection(
    config_xml: str,
    nodes_xml: str,
    status_xml: str,
    programs_xml: str,
    time_xml: str,
    var_defs_xml: list[str],
    var_values_xml: str,
) -> FakeConnection:
    return FakeConnection(
        config=config_xml,
        nodes=nodes_xml,
        status=status_xml,
        programs=programs_xml,
        time=time_xml,
        var_defs=var_defs_xml,
        var_values=var_values_xml,
    )


@pytest.fixture
async def build_isy(
    config_xml: str,
    time_xml: str,
    programs_xml: str,
    var_defs_xml: list[str],
    var_values_xml: str,
):
    """Factory: build a fresh ``ISY`` from arbitrary nodes/status XML.

    Useful for feature-specific fixtures (thermostat, lock, etc.) where the
    full eisy export is overkill.
    """
    created: list[ISY] = []

    async def _build(nodes_xml: str, status_xml: str) -> ISY:
        conn = FakeConnection(
            config=config_xml,
            nodes=nodes_xml,
            status=status_xml,
            programs=programs_xml,
            time=time_xml,
            var_defs=var_defs_xml,
            var_values=var_values_xml,
        )
        isy = ISY(address="127.0.0.1", port=80, username="u", password="p")
        await isy.conn.close()
        isy.conn = conn  # type: ignore[assignment]
        await isy.initialize()
        created.append(isy)
        return isy

    try:
        yield _build
    finally:
        for isy in created:
            await isy.shutdown()


@pytest.fixture
async def isy(fake_connection: FakeConnection) -> ISY:
    """A fully-initialized ``ISY`` backed by ``FakeConnection``."""
    isy = ISY(
        address="127.0.0.1",
        port=80,
        username="u",
        password="p",
    )
    # Replace the real connection before initialize() touches the network.
    await isy.conn.close()
    isy.conn = fake_connection  # type: ignore[assignment]
    await isy.initialize()
    try:
        yield isy
    finally:
        # FakeConnection.close is an AsyncMock; shutdown() awaits it cleanly.
        await isy.shutdown()
