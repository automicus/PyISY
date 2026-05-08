"""Tests for :mod:`pyisy.connection`."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from aioresponses import aioresponses

from pyisy.connection import (
    MAX_HTTP_CONNECTIONS_IOX,
    MAX_HTTP_CONNECTIONS_ISY,
    Connection,
    can_https,
)
from pyisy.exceptions import ISYConnectionError, ISYInvalidAuthError


@pytest.fixture
async def conn() -> Connection:
    c = Connection(
        address="127.0.0.1",
        port=80,
        username="u",
        password="p",
        use_https=False,
    )
    try:
        yield c
    finally:
        await c.close()


async def test_url_includes_webroot() -> None:
    c = Connection(address="host", port=8080, username="u", password="p", webroot="/api/")
    try:
        assert c.url == "http://host:8080/api"
    finally:
        await c.close()


async def test_compile_url_quotes_path_segments(conn: Connection) -> None:
    url = conn.compile_url(["nodes", "AB CD 12 1"])
    assert "AB%20CD%2012%201" in url


async def test_increase_available_connections_raises_semaphore(
    conn: Connection,
) -> None:
    # The semaphore exposes its remaining count via private attr; we just
    # verify it changed after the increase call.
    starting_value = conn.semaphore._value  # type: ignore[attr-defined]
    assert starting_value == MAX_HTTP_CONNECTIONS_ISY
    conn.increase_available_connections()
    assert conn.semaphore._value == MAX_HTTP_CONNECTIONS_IOX  # type: ignore[attr-defined]


def test_can_https_rejects_unsupported_tls_version() -> None:
    assert can_https(1.0) is False
    assert can_https("garbage") is False


def test_can_https_accepts_auto_and_supported_versions() -> None:
    # "auto" is the new default and lets OpenSSL negotiate the highest
    # mutually-supported TLS version (floor 1.2). The numeric values are
    # still accepted for backward compat (deprecated; see #494).
    assert can_https("auto") is True
    assert isinstance(can_https(1.1), bool)
    assert isinstance(can_https(1.2), bool)
    assert isinstance(can_https(1.3), bool)


async def test_connection_info_contents(conn: Connection) -> None:
    info = conn.connection_info
    assert info["addr"] == "127.0.0.1"
    assert info["port"] == 80
    assert info["passwd"] == "p"
    assert "auth" in info


async def test_request_401_raises_invalid_auth(conn: Connection) -> None:
    """A ``401 Unauthorized`` from the controller must surface as
    ``ISYInvalidAuthError`` rather than being silently retried."""
    url = conn.compile_url(["config"])
    with aioresponses() as mocked:
        mocked.get(url, status=401, repeat=True)
        with pytest.raises(ISYInvalidAuthError):
            await conn.request(url)


async def test_test_connection_raises_when_config_unreachable(
    conn: Connection,
) -> None:
    """``test_connection`` re-raises as ``ISYConnectionError`` when the
    config endpoint never responds — this is what ``ISY.initialize`` relies
    on to fail fast on bad creds / unreachable host."""
    import aiohttp

    url = conn.compile_url(["config"])
    with aioresponses() as mocked:
        # aiohttp.ClientError is caught by Connection.request and re-raised
        # as ISYConnectionError when retries=None (the test_connection path).
        mocked.get(url, exception=aiohttp.ClientConnectionError("boom"))
        with pytest.raises(ISYConnectionError):
            await conn.test_connection()


async def test_request_404_returns_none_without_retry404(conn: Connection) -> None:
    """A plain 404 (no ``retry404=True``) must return ``None`` without
    falling into the retry/backoff loop."""
    url = conn.compile_url(["nodes", "missing"])
    with aioresponses() as mocked:
        mocked.get(url, status=404)
        result = await conn.request(url)
    assert result is None


async def test_request_404_with_ok404_returns_empty_string(conn: Connection) -> None:
    """``ok404=True`` makes 404 a success indicator returning ``""`` — used by
    ``ping`` / ``get_network`` where a 404 means "feature not present"."""
    url = conn.compile_url(["network", "resources"])
    with aioresponses() as mocked:
        mocked.get(url, status=404)
        result = await conn.request(url, ok404=True)
    assert result == ""


async def test_request_200_returns_body(conn: Connection) -> None:
    url = conn.compile_url(["config"])
    body = "<configuration><x/></configuration>"
    with aioresponses() as mocked:
        mocked.get(url, status=200, body=body)
        result = await conn.request(url)
    assert result == body


@pytest.mark.parametrize(
    ("kwargs", "expected_scheme"),
    [
        ({"use_https": False}, "http://"),
        ({"use_https": True}, "https://"),
    ],
)
async def test_url_scheme_matches_use_https(kwargs: dict, expected_scheme: str) -> None:
    # Avoid creating a real HTTPS session for the https case — patch the
    # session factory so this test stays purely synchronous.
    with (
        patch("pyisy.connection.get_new_client_session"),
        patch("pyisy.connection.get_sslcontext", return_value=None),
    ):
        c = Connection(address="h", port=1, username="u", password="p", **kwargs)
    assert c.url.startswith(expected_scheme)
