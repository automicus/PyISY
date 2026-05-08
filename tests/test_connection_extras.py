"""Tests for the rest of :mod:`pyisy.connection` — the ``get_*`` REST
wrappers, ``request`` retry / 503 / ClientResponseError branches,
``compile_url`` query strings, and the SSL/TLS helpers.
"""

from __future__ import annotations

import ssl
import warnings
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from aioresponses import aioresponses

from pyisy.connection import (
    EMPTY_XML_RESPONSE,
    OP_LEGACY_SERVER_CONNECT,
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


def test_get_sslcontext_auto_pins_min_v12_no_max() -> None:
    """``tls_ver='auto'`` (the new default) builds a PROTOCOL_TLS_CLIENT
    context with ``min=TLSv1_2`` and no max pin, so OpenSSL negotiates
    the highest mutually-supported version. eisy/Polisy lands on TLS 1.3,
    stock ISY-994 (4.5.4+) lands on TLS 1.2.

    Verifies #494 acceptance criteria: no ``DeprecationWarning`` from
    PyISY's own code and no Python ``ssl`` deprecation noise either,
    since both 1.2 and 1.3 are supported moderns."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        ctx = get_sslcontext(use_https=True)  # default tls_ver="auto"

    assert ctx is not None
    assert ctx.minimum_version == ssl.TLSVersion.TLSv1_2
    assert ctx.maximum_version == ssl.TLSVersion.MAXIMUM_SUPPORTED
    # Self-signed eisy/Polisy out-of-the-box default.
    assert ctx.verify_mode == ssl.CERT_NONE
    assert ctx.check_hostname is False


def test_get_sslcontext_does_not_preset_legacy_renegotiation() -> None:
    """``OP_LEGACY_SERVER_CONNECT`` (the ISY-994 RFC-5746 compat flag)
    must NOT be set by default — modern peers (eisy/Polisy IoX, ISY-994
    firmware that honors RFC 5746) keep strict TLS. The flag is enabled
    on demand by ``Connection.request()`` only when the peer rejects
    the handshake with ``UNSAFE_LEGACY_RENEGOTIATION_DISABLED``."""
    ctx = get_sslcontext(use_https=True)
    assert ctx is not None
    assert not (ctx.options & OP_LEGACY_SERVER_CONNECT)


def test_get_sslcontext_verify_ssl_true_flips_cert_verification() -> None:
    """``verify_ssl=True`` is the opt-in for users who installed a
    properly-signed cert on their controller. It flips both
    ``verify_mode`` and ``check_hostname``."""
    ctx = get_sslcontext(use_https=True, verify_ssl=True)
    assert ctx is not None
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True


@pytest.mark.parametrize("tls_ver", [1.1, 1.2, 1.3])
def test_get_sslcontext_numeric_pin_emits_deprecation_warning(tls_ver: float) -> None:
    """Numeric ``tls_ver`` values still build a context for backward
    compat (an ISY-994 manually downgraded below 1.2 still needs 1.1)
    but PyISY emits exactly one ``DeprecationWarning`` per call to
    nudge callers toward ``"auto"``."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        ctx = get_sslcontext(use_https=True, tls_ver=tls_ver)

    pyisy_warns = [w for w in caught if "tls_ver" in str(w.message)]
    assert len(pyisy_warns) == 1
    assert issubclass(pyisy_warns[0].category, DeprecationWarning)

    # Numeric pin still produces a working context, with min == max.
    assert ctx is not None
    assert ctx.minimum_version == ctx.maximum_version


def test_get_sslcontext_rejects_unknown_value() -> None:
    """Unsupported numeric or string values raise ValueError instead of
    silently falling through (the old code path raised ``UnboundLocalError``
    on a bad input — see #494)."""
    with pytest.raises(ValueError, match="Unsupported TLS version"):
        get_sslcontext(use_https=True, tls_ver=1.0)
    with pytest.raises(ValueError, match="Unsupported TLS version"):
        get_sslcontext(use_https=True, tls_ver="bogus")  # type: ignore[arg-type]


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


async def test_get_variable_defs_passes_ok404(conn: Connection) -> None:
    """Both per-type requests must be issued with ``ok404=True`` so a
    factory-reset / un-configured ISY-994 doesn't surface its
    ``/CONF/INTEGER.VAR not found`` 404 as ERROR-level log spam — the
    Variables parser already treats that body as "no variables
    defined"."""
    conn.request = AsyncMock(return_value="")
    await conn.get_variable_defs()
    assert conn.request.await_count == 2
    for call in conn.request.await_args_list:
        assert call.kwargs.get("ok404") is True


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


async def test_request_client_response_error_with_ok404_returns_empty(
    conn: Connection,
) -> None:
    """Regression: ISY-994 firmware on a factory-reset controller answers
    missing optional resources (``/CONF/STATE.VAR``,
    ``/CONF/NET/RES.CFG``) with a real 404 whose framing desyncs the
    keep-alive connection — aiohttp's parser then raises
    ``ClientResponseError("Expected HTTP/, RTSP/ or ICE/:")`` on the
    *next* request that reuses the socket. Callers that already opted
    into ``ok404=True`` (variable defs, network resources) should see
    that absorbed as ``""`` rather than an ERROR-level log + None."""
    url = conn.compile_url(["vars", "definitions", "1"])
    with aioresponses() as mocked:
        mocked.get(
            url,
            exception=aiohttp.ClientResponseError(
                request_info=None,
                history=(),
                status=400,
                message="Expected HTTP/, RTSP/ or ICE/:",
            ),
        )
        result = await conn.request(url, ok404=True)
    assert result == ""


async def test_request_ssl_error_always_raises_connection_error(
    conn: Connection,
) -> None:
    """SSL/TLS handshake failures are non-recoverable config mismatches
    (controller pinned below auto-floor TLS 1.2, or ``verify_ssl=True``
    against a self-signed cert). ``request`` must raise
    ``ISYConnectionError`` rather than logging + returning ``None``,
    even on the retry path — retrying a handshake that failed for a
    protocol/cert reason won't help, and callers (HA Core) need a
    definitive failure to translate into ``ConfigEntryNotReady``
    instead of treating it as a transient miss.

    The raise replaces the previous opaque
    ``ClientOSError`` → DEBUG "ISY not ready or closed connection."
    branch that silently ate ``ClientConnectorSSLError`` (a subclass).
    The SSL detail rides along in ``__cause__`` and the exception
    message — no separate WARNING/ERROR log so we don't double up."""
    from unittest.mock import MagicMock

    from pyisy.exceptions import ISYConnectionError

    url = conn.compile_url(["status"])
    ssl_err = aiohttp.ClientConnectorSSLError(
        MagicMock(),
        ssl.SSLError(1, "[SSL: UNSUPPORTED_PROTOCOL] unsupported protocol"),
    )
    with aioresponses() as mocked:
        mocked.get(url, exception=ssl_err)
        with pytest.raises(ISYConnectionError, match="SSL/TLS error") as excinfo:
            await conn.request(url)
    # Cause chain preserves the original aiohttp SSL error for
    # callers / log handlers that want to introspect it.
    assert isinstance(excinfo.value.__cause__, aiohttp.ClientSSLError)


async def test_request_ssl_error_raises_on_test_connection_path(
    conn: Connection,
) -> None:
    """Same behavior on the ``retries=None`` path used by
    ``test_connection`` / ``ISY.initialize`` — verifying the SSL branch
    is taken before the (formerly raise-on-retries-None) generic
    ``ClientOSError`` branch."""
    from unittest.mock import MagicMock

    from pyisy.exceptions import ISYConnectionError

    url = conn.compile_url(["config"])
    ssl_err = aiohttp.ClientConnectorSSLError(MagicMock(), ssl.SSLError(1, "unsupported protocol"))
    with aioresponses() as mocked:
        mocked.get(url, exception=ssl_err)
        with pytest.raises(ISYConnectionError, match="SSL/TLS error"):
            await conn.request(url, retries=None)


async def test_request_legacy_reneg_failure_enables_compat_and_retries() -> None:
    """First handshake fails with ``UNSAFE_LEGACY_RENEGOTIATION_DISABLED``
    (signature of ISY-994's pre-RFC-5746 TLS stack against modern OpenSSL).
    ``request()`` must:

    1. Flip ``OP_LEGACY_SERVER_CONNECT`` on the existing SSL context
       (modern peers — eisy/Polisy IoX, ISY-994 firmware that honors
       RFC 5746 — never reach this branch and stay strict).
    2. Log a one-time WARNING explaining the degradation.
    3. Retry the request and surface the second response normally.
    """
    from unittest.mock import MagicMock

    https_conn = Connection(address="h", port=443, username="u", password="p", use_https=True)
    try:
        # Sanity: flag is OFF on a fresh connection (verifies the
        # context-builder default; the request-path retry is what
        # actually flips it).
        assert https_conn.sslcontext is not None
        assert not (https_conn.sslcontext.options & OP_LEGACY_SERVER_CONNECT)

        url = https_conn.compile_url(["config"])
        reneg_err = aiohttp.ClientConnectorSSLError(
            MagicMock(),
            ssl.SSLError(
                1,
                "[SSL: UNSAFE_LEGACY_RENEGOTIATION_DISABLED] unsafe legacy renegotiation disabled",
            ),
        )
        with aioresponses() as mocked:
            # First call: handshake refusal. Second call (after the
            # retry flips the flag): success.
            mocked.get(url, exception=reneg_err)
            mocked.get(url, status=200, body="<configuration/>")
            result = await https_conn.request(url)

        assert result == "<configuration/>"
        assert https_conn.sslcontext.options & OP_LEGACY_SERVER_CONNECT
    finally:
        await https_conn.close()


async def test_request_legacy_reneg_does_not_trigger_for_unrelated_ssl_errors() -> None:
    """Only the specific ``UNSAFE_LEGACY_RENEGOTIATION_DISABLED``
    failure flips the flag. A generic protocol error
    (``UNSUPPORTED_PROTOCOL``, cert verify failure, etc.) must surface
    as ``ISYConnectionError`` without weakening the SSL context — those
    are real config mismatches the user needs to fix, not ISY-994
    legacy compat."""
    from unittest.mock import MagicMock

    from pyisy.exceptions import ISYConnectionError

    https_conn = Connection(address="h", port=443, username="u", password="p", use_https=True)
    try:
        url = https_conn.compile_url(["config"])
        proto_err = aiohttp.ClientConnectorSSLError(
            MagicMock(),
            ssl.SSLError(1, "[SSL: UNSUPPORTED_PROTOCOL] unsupported protocol"),
        )
        with aioresponses() as mocked:
            mocked.get(url, exception=proto_err)
            with pytest.raises(ISYConnectionError, match="SSL/TLS error"):
                await https_conn.request(url)

        # Flag must remain OFF — the user's security posture isn't
        # silently weakened on every SSL failure.
        assert https_conn.sslcontext is not None
        assert not (https_conn.sslcontext.options & OP_LEGACY_SERVER_CONNECT)
    finally:
        await https_conn.close()


async def test_request_non_rest_url_does_not_crash(conn: Connection) -> None:
    """Regression for #488: ``request()`` derives its debug-log endpoint
    from the URL by splitting on ``"rest"``. ``get_description()`` builds
    a ``/desc`` URL that lacks that substring, so the happy path used to
    raise ``IndexError`` before the body could be returned."""
    url = "http://h:80/desc"
    with aioresponses() as mocked:
        mocked.get(url, status=200, body="<root/>")
        result = await conn.request(url)
    assert result == "<root/>"


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
