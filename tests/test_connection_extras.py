"""Tests for the rest of :mod:`pyisy.connection` — the ``get_*`` REST
wrappers, ``request`` retry / 503 / ClientResponseError branches,
``compile_url`` query strings, and the SSL/TLS helpers.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from aioresponses import aioresponses

from pyisy.connection import (
    EMPTY_XML_RESPONSE,
    Connection,
    get_sslcontext,
)


@pytest.fixture
async def conn() -> Connection:
    c = Connection(address="h", port=80, username="u", password="p")
    try:
        yield c
    finally:
        await c.close()


# -- compile_url query branch + helpers ------------------------------


async def test_compile_url_appends_query_string(conn: Connection) -> None:
    url = conn.compile_url(["nodes"], {"members": "false"})
    assert url.endswith("/rest/nodes?members=false")


def test_get_sslcontext_returns_none_for_http() -> None:
    assert get_sslcontext(use_https=False) is None


def test_get_sslcontext_tls_1_2_returns_context() -> None:
    """TLS 1.2 path is the modern eisy / IoX default. Older 1.1 path is
    exercised by the existing ``test_can_https_*`` tests."""
    ctx = get_sslcontext(use_https=True, tls_ver=1.2)
    assert ctx is not None


# -- get_* REST wrappers ---------------------------------------------


async def test_ping_returns_true_on_response(conn: Connection) -> None:
    """``ping`` calls ``/rest/ping`` with ``ok404=True`` and returns
    True if the controller responds at all (200 or 404 are both
    "alive")."""
    url = conn.compile_url(["ping"])
    with aioresponses() as mocked:
        mocked.get(url, status=200, body="<x/>")
        assert await conn.ping() is True


async def test_ping_returns_false_on_unreachable(conn: Connection) -> None:
    """Note: with ok404=True, request() returns "" on 404 → not None,
    so ping returns True. Use a connection error to simulate
    unreachable."""
    url = conn.compile_url(["ping"])
    with aioresponses() as mocked:
        mocked.get(url, exception=aiohttp.ClientConnectionError("boom"), repeat=True)
        assert await conn.ping() is False


async def test_get_description_builds_desc_path(conn: Connection) -> None:
    """``get_description`` is special — it builds its own URL outside
    ``/rest/`` and points at the UPnP-style ``/desc`` document. We
    stub ``request`` directly because the real ``request`` crashes on
    URLs that don't contain ``"rest"`` (filed as #488); once that's
    fixed, this test can switch to an aioresponses round-trip."""
    conn.request = AsyncMock(return_value="<root/>")
    result = await conn.get_description()
    url = conn.request.await_args.args[0]
    assert url.endswith("/desc")
    assert result == "<root/>"


async def test_get_programs_with_address_appends_to_path(conn: Connection) -> None:
    """When an address is supplied, ``get_programs(address="0007")``
    fetches ``/rest/programs/0007?subfolders=true``."""
    conn.request = AsyncMock(return_value="<programs/>")
    await conn.get_programs(address="0007")
    url = conn.request.await_args.args[0]
    assert "/programs/0007" in url
    assert "subfolders=true" in url


async def test_get_programs_without_address_fetches_root(conn: Connection) -> None:
    conn.request = AsyncMock(return_value="<programs/>")
    await conn.get_programs()
    url = conn.request.await_args.args[0]
    assert url.endswith("/rest/programs?subfolders=true")


async def test_get_nodes_includes_members_false_query(conn: Connection) -> None:
    conn.request = AsyncMock(return_value="<nodes/>")
    await conn.get_nodes()
    url = conn.request.await_args.args[0]
    assert "/rest/nodes" in url
    assert "members=false" in url


async def test_get_status_path(conn: Connection) -> None:
    conn.request = AsyncMock(return_value="<nodes/>")
    await conn.get_status()
    assert "/rest/status" in conn.request.await_args.args[0]


async def test_get_time_path(conn: Connection) -> None:
    conn.request = AsyncMock(return_value="<DT/>")
    await conn.get_time()
    assert "/rest/time" in conn.request.await_args.args[0]


async def test_get_variable_defs_returns_two_responses(conn: Connection) -> None:
    """``get_variable_defs`` issues both type-1 and type-2 requests in
    parallel via ``asyncio.gather`` and returns a list of two strings."""
    conn.request = AsyncMock(return_value="<CList/>")
    result = await conn.get_variable_defs()
    assert isinstance(result, list)
    assert len(result) == 2
    assert conn.request.await_count == 2


async def test_get_variables_concatenates_and_strips_inner_boundary(
    conn: Connection,
) -> None:
    """``get_variables`` fetches ``/vars/get/1`` and ``/vars/get/2``,
    concatenates the two responses, and strips the inner
    ``</vars><?xml ...><vars>`` boundary so the result is a single
    valid ``<vars>...</vars>`` document."""
    type1 = '<?xml version="1.0" encoding="UTF-8"?><vars><var type="1" id="1"/></vars>'
    type2 = '<?xml version="1.0" encoding="UTF-8"?><vars><var type="2" id="1"/></vars>'

    async def fake_request(url, **kwargs):
        return type1 if "/get/1" in url else type2

    conn.request = AsyncMock(side_effect=fake_request)
    result = await conn.get_variables()
    # The boundary should be stripped — one contiguous <vars>…</vars>.
    assert result.count("<vars>") == 1
    assert result.count("</vars>") == 1


async def test_get_network_returns_none_when_empty(conn: Connection) -> None:
    """``get_network`` uses ``ok404=True`` → returns ``""`` on 404, but
    the wrapper coerces that to ``None`` so callers can detect "feature
    not present" with a single ``is None`` check."""
    conn.request = AsyncMock(return_value="")
    assert await conn.get_network() is None


async def test_get_network_returns_xml_on_success(conn: Connection) -> None:
    conn.request = AsyncMock(return_value="<NetConfig/>")
    assert await conn.get_network() == "<NetConfig/>"


# -- request() failure / retry branches ------------------------------


async def test_request_503_falls_through_to_retry_and_returns_none(
    conn: Connection,
) -> None:
    """A 503 is logged and the loop falls through to the retry/backoff
    branch. With backoff exhausted (5 retries x small sleep), the
    function eventually returns None."""
    url = conn.compile_url(["status"])
    with aioresponses() as mocked, patch("pyisy.connection.RETRY_BACKOFF", [0, 0, 0, 0, 0]):
        mocked.get(url, status=503, repeat=True)
        result = await conn.request(url)
    assert result is None


async def test_request_empty_xml_response_falls_through_to_retry(
    conn: Connection,
) -> None:
    """A 200 OK with ``<?xml ... ?>`` and nothing else is treated as
    "controller serving stale empty doc" and falls into retry/backoff."""
    url = conn.compile_url(["nodes"])
    with aioresponses() as mocked, patch("pyisy.connection.RETRY_BACKOFF", [0, 0, 0, 0, 0]):
        mocked.get(url, status=200, body=EMPTY_XML_RESPONSE, repeat=True)
        result = await conn.request(url)
    assert result is None


async def test_request_client_response_error_returns_none(conn: Connection) -> None:
    """Malformed framing / protocol errors (``ClientResponseError``)
    are not retried — the controller is broken in a way that won't
    recover. Returns None unless ``retries=None``."""
    url = conn.compile_url(["nodes"])
    with aioresponses() as mocked:
        mocked.get(
            url,
            exception=aiohttp.ClientResponseError(request_info=None, history=(), status=502, message="bad"),
        )
        result = await conn.request(url)
    assert result is None


async def test_request_retry404_eventually_returns_none(conn: Connection) -> None:
    """``retry404=True`` from #184 makes 404s fall into the retry loop
    instead of returning immediately. After the retry budget is spent
    the result is still None."""
    url = conn.compile_url(["nodes", "X", "cmd", "DON"])
    with aioresponses() as mocked, patch("pyisy.connection.RETRY_BACKOFF", [0, 0, 0, 0, 0]):
        mocked.get(url, status=404, repeat=True)
        result = await conn.request(url, retry404=True)
    assert result is None


async def test_test_connection_returns_config_on_success(conn: Connection) -> None:
    url = conn.compile_url(["config"])
    body = "<configuration/>"
    with aioresponses() as mocked:
        mocked.get(url, status=200, body=body)
        result = await conn.test_connection()
    assert result == body
