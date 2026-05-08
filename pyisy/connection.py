"""Connection to the ISY."""

from __future__ import annotations

import asyncio
import ssl
import warnings
from typing import Literal
from urllib.parse import quote, urlencode

import aiohttp

from .constants import (
    METHOD_GET,
    URL_CLOCK,
    URL_CONFIG,
    URL_DEFINITIONS,
    URL_MEMBERS,
    URL_NETWORK,
    URL_NODES,
    URL_PING,
    URL_PROGRAMS,
    URL_RESOURCES,
    URL_STATUS,
    URL_SUBFOLDERS,
    URL_VARIABLES,
    VAR_INTEGER,
    VAR_STATE,
    XML_FALSE,
    XML_TRUE,
)
from .exceptions import ISYConnectionError, ISYInvalidAuthError
from .logging import _LOGGER, enable_logging

TLSVer = float | Literal["auto"]

MAX_HTTPS_CONNECTIONS_ISY = 2
MAX_HTTP_CONNECTIONS_ISY = 5
MAX_HTTPS_CONNECTIONS_IOX = 20
MAX_HTTP_CONNECTIONS_IOX = 50

MAX_RETRIES = 5
RETRY_BACKOFF = [0.01, 0.10, 0.25, 1, 2]  # Seconds

HTTP_OK = 200  # Valid request received, will run it
HTTP_UNAUTHORIZED = 401  # User authentication failed
HTTP_NOT_FOUND = 404  # Unrecognized request received and ignored
HTTP_SERVICE_UNAVAILABLE = 503  # Valid request received, system too busy to run it

HTTP_TIMEOUT = 30

HTTP_HEADERS = {
    "Connection": "keep-alive",
    "Keep-Alive": "5000",
    "Accept-Encoding": "gzip, deflate",
}

EMPTY_XML_RESPONSE = '<?xml version="1.0" encoding="UTF-8"?>'

# ``ssl.OP_LEGACY_SERVER_CONNECT`` was added to the stdlib ``ssl``
# module in Python 3.12; CI still runs on 3.11. The underlying OpenSSL
# flag ``SSL_OP_LEGACY_SERVER_CONNECT`` has had the stable value
# ``0x4`` for years, so fall back to the literal when the attribute is
# missing.
OP_LEGACY_SERVER_CONNECT = getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)


class Connection:
    """Connection object to manage connection to and interaction with ISY."""

    def __init__(
        self,
        address: str,
        port: int,
        username: str,
        password: str,
        use_https: bool = False,
        tls_ver: TLSVer = "auto",
        webroot: str = "",
        websession: aiohttp.ClientSession | None = None,
        verify_ssl: bool = False,
    ) -> None:
        """Initialize the Connection object."""
        if len(_LOGGER.handlers) == 0:
            enable_logging(add_null_handler=True)

        self._address = address
        self._port = port
        self._username = username
        self._password = password
        self._auth = aiohttp.BasicAuth(self._username, self._password)
        self._webroot = webroot.rstrip("/")
        self.req_session = websession
        self._tls_ver = tls_ver
        self.use_https = use_https
        self._url = f"http{'s' if self.use_https else ''}://{self._address}:{self._port}{self._webroot}"

        self.semaphore = asyncio.Semaphore(
            MAX_HTTPS_CONNECTIONS_ISY if use_https else MAX_HTTP_CONNECTIONS_ISY
        )

        if websession is None:
            websession = get_new_client_session(use_https, tls_ver)
        self.req_session = websession
        self.sslcontext = get_sslcontext(use_https, tls_ver, verify_ssl)

    async def test_connection(self) -> str | None:
        """Test the connection and get the config for the ISY."""
        config = await self.get_config(retries=None)
        if not config:
            raise ISYConnectionError("Could not connect to the ISY with the parameters provided.")
        return config

    def increase_available_connections(self) -> None:
        """Increase the number of allowed connections for newer hardware."""
        _LOGGER.debug("Increasing available simultaneous connections")
        self.semaphore = asyncio.Semaphore(
            MAX_HTTPS_CONNECTIONS_IOX if self.use_https else MAX_HTTP_CONNECTIONS_IOX
        )

    async def close(self) -> None:
        """Cleanup connections and prepare for exit."""
        await self.req_session.close()

    @property
    def connection_info(self) -> dict[str, str | int | bytes | None]:
        """Return the connection info required to connect to the ISY."""
        connection_info = {}
        connection_info["auth"] = self._auth.encode()
        connection_info["addr"] = self._address
        connection_info["port"] = int(self._port)
        connection_info["passwd"] = self._password
        connection_info["webroot"] = self._webroot
        if self.use_https and self._tls_ver:
            connection_info["tls"] = self._tls_ver

        return connection_info

    @property
    def url(self) -> str:
        """Return the full connection url."""
        return self._url

    # COMMON UTILITIES
    def compile_url(self, path: list[str], query: str | None = None) -> str:
        """Compile the URL to fetch from the ISY."""
        url = self.url
        if path is not None:
            url += "/rest/" + "/".join([quote(item) for item in path])

        if query is not None:
            url += "?" + urlencode(query)

        return url

    async def request(
        self,
        url: str,
        retries: int = 0,
        ok404: bool = False,
        delay: int = 0,
        retry404: bool = False,
    ) -> str | None:
        """Execute request to ISY REST interface.

        retry404: ISY-994 returns spurious 404s on `/rest/nodes/.../cmd/...`
        when the Insteon network is overwhelmed. Pass True from command-issuing
        callers so a 404 falls into the existing retry/backoff loop instead of
        being treated as a permanent failure.
        """
        _LOGGER.debug("ISY Request: %s", url)
        if delay:
            await asyncio.sleep(delay)
        try:
            async with (
                self.semaphore,
                self.req_session.get(
                    url,
                    auth=self._auth,
                    headers=HTTP_HEADERS,
                    timeout=HTTP_TIMEOUT,
                    ssl=self.sslcontext,
                ) as res,
            ):
                # /desc and other non-/rest URLs lack the "rest" substring.
                _, _, endpoint = url.partition("rest")
                if not endpoint:
                    endpoint = url
                if res.status == HTTP_OK:
                    _LOGGER.debug("ISY Response Received: %s", endpoint)
                    results = await res.text(encoding="utf-8", errors="ignore")
                    if results != EMPTY_XML_RESPONSE:
                        return results
                    _LOGGER.debug("Invalid empty XML returned: %s", endpoint)
                    res.release()
                if res.status == HTTP_NOT_FOUND:
                    if ok404:
                        _LOGGER.debug("ISY Response Received %s", endpoint)
                        res.release()
                        return ""
                    if retry404:
                        # ISY-994 emits spurious 404s when the Insteon network
                        # is busy; fall through to the retry/backoff loop.
                        _LOGGER.debug(
                            "ISY returned 404 for %s; controller may be busy, will retry",
                            endpoint,
                        )
                        res.release()
                    else:
                        _LOGGER.error("ISY Reported an Invalid Command Received %s", endpoint)
                        res.release()
                        return None
                if res.status == HTTP_UNAUTHORIZED:
                    res.release()
                    raise ISYInvalidAuthError("Invalid credentials provided for ISY connection.")
                if res.status == HTTP_SERVICE_UNAVAILABLE:
                    _LOGGER.warning("ISY too busy to process request %s", endpoint)
                    res.release()

        except TimeoutError:
            _LOGGER.warning("Timeout while trying to connect to the ISY.")
        except aiohttp.ClientSSLError as err:
            # SSL/TLS handshake failure. Subclass of ``ClientOSError``, so
            # the broader branch below would otherwise eat it silently as
            # a generic "ISY not ready or closed connection." debug.
            # Almost always one of:
            #   * controller pinned below the ``tls_ver='auto'`` floor of
            #     TLS 1.2 (e.g. an ISY-994 manually downgraded to 1.1, or
            #     a modern OpenSSL distro with ``MinProtocol=TLSv1.2``).
            #   * ``verify_ssl=True`` against the controller's self-signed
            #     cert (``ClientConnectorCertificateError``).
            #   * ISY-994 firmware (pre-RFC-5746) rejected by OpenSSL 3.x
            #     with ``UNSAFE_LEGACY_RENEGOTIATION_DISABLED``. We
            #     identify ISY-994 by the failure itself (the only peer
            #     class that fails this way) and degrade the SSL context
            #     once for the lifetime of the ``Connection`` — modern
            #     peers (eisy/Polisy IoX, ISY-994 firmware that does
            #     RFC 5746) stay strict.
            if (
                self.sslcontext is not None
                and not (self.sslcontext.options & OP_LEGACY_SERVER_CONNECT)
                and "UNSAFE_LEGACY_RENEGOTIATION_DISABLED" in str(err)
            ):
                _LOGGER.warning(
                    "Enabling ISY-994 legacy-renegotiation TLS compatibility for "
                    "this controller; eisy/Polisy IoX peers do not need this. "
                    "Original error: %s",
                    err,
                )
                self.sslcontext.options |= OP_LEGACY_SERVER_CONNECT
                return await self.request(url, retries=retries, ok404=ok404, delay=delay, retry404=retry404)
            # Always raise — retrying a real version/cert mismatch won't
            # recover, and callers (HA Core) need a definitive failure
            # to translate into ``ConfigEntryNotReady`` rather than a
            # silent ``None`` that looks like a transient miss. The SSL
            # detail rides along in the exception chain.
            raise ISYConnectionError(f"SSL/TLS error: {err}") from err
        except (
            aiohttp.ClientOSError,
            aiohttp.ServerDisconnectedError,
        ):
            _LOGGER.debug("ISY not ready or closed connection.")
        except aiohttp.ClientResponseError as err:
            # Malformed framing/protocol error — retrying won't recover.
            # When the caller already opted into ``ok404=True`` we treat it
            # as another flavor of "feature not present": ISY-994 firmware
            # on a factory-reset / un-configured controller responds to
            # missing optional resources (``/CONF/STATE.VAR``,
            # ``/CONF/NET/RES.CFG``) with a real 404 whose framing trips
            # aiohttp's parser when the connection is reused — the next
            # request on the kept-alive socket reads the prior 404's HTML
            # body where an HTTP status line should be. Demote that to a
            # debug log and return ``""`` so the optional manager's
            # "no resource configured" path handles it cleanly.
            if ok404:
                _LOGGER.debug(
                    "ISY response framing error on optional endpoint %s: %s",
                    url,
                    err.message,
                )
                return ""
            _LOGGER.error(
                "Client Response Error from ISY: %s %s.",
                err.status,
                err.message,
            )
            if retries is None:
                raise ISYConnectionError from err
            return None
        except aiohttp.ClientError as err:
            _LOGGER.error(
                "ISY Could not receive response from device because of a network issue: %s",
                type(err),
            )

        if retries is None:
            raise ISYConnectionError
        if retries < MAX_RETRIES:
            _LOGGER.debug(
                "Retrying ISY Request in %ss, retry %s.",
                RETRY_BACKOFF[retries],
                retries + 1,
            )
            # sleep to allow the ISY to catch up
            await asyncio.sleep(RETRY_BACKOFF[retries])
            # recurse to try again
            return await self.request(url, retries + 1, ok404=ok404, retry404=retry404)
        # fail for good
        _LOGGER.error(
            "Bad ISY Request: (%s) Failed after %s retries.",
            url,
            retries,
        )
        return None

    async def ping(self) -> bool:
        """Test connection to the ISY and return True if alive."""
        req_url = self.compile_url([URL_PING])
        result = await self.request(req_url, ok404=True)
        return result is not None

    async def get_description(self) -> str | None:
        """Fetch the services description from the ISY."""
        url = "https://" if self.use_https else "http://"
        url += f"{self._address}:{self._port}{self._webroot}/desc"
        return await self.request(url)

    async def get_config(self, retries: int = 0) -> str | None:
        """Fetch the configuration from the ISY."""
        req_url = self.compile_url([URL_CONFIG])
        return await self.request(req_url, retries=retries)

    async def get_programs(self, address: int | str | None = None) -> str | None:
        """Fetch the list of programs from the ISY."""
        addr = [URL_PROGRAMS]
        if address is not None:
            addr.append(str(address))
        req_url = self.compile_url(addr, {URL_SUBFOLDERS: XML_TRUE})
        return await self.request(req_url)

    async def get_nodes(self) -> str | None:
        """Fetch the list of nodes/groups/scenes from the ISY."""
        req_url = self.compile_url([URL_NODES], {URL_MEMBERS: XML_FALSE})
        return await self.request(req_url)

    async def get_status(self) -> str | None:
        """Fetch the status of nodes/groups/scenes from the ISY."""
        req_url = self.compile_url([URL_STATUS])
        return await self.request(req_url)

    async def get_variable_defs(self) -> list[str | BaseException] | None:
        """Fetch the list of variables from the ISY.

        ``ok404=True`` because both endpoints legitimately 404 on a
        factory-reset / un-configured ISY-994 (``/CONF/INTEGER.VAR not
        found`` / ``/CONF/STATE.VAR not found``); the ``Variables``
        parser already handles those bodies and ``None`` as
        "no variables defined" (see ``EMPTY_VARIABLE_RESPONSES``).
        Without ``ok404`` the request path emits ERROR-level log spam
        for what is really an empty-config success.
        """
        req_list = [
            [URL_VARIABLES, URL_DEFINITIONS, VAR_INTEGER],
            [URL_VARIABLES, URL_DEFINITIONS, VAR_STATE],
        ]
        req_urls = [self.compile_url(req) for req in req_list]
        return await asyncio.gather(
            *[self.request(req_url, ok404=True) for req_url in req_urls],
            return_exceptions=True,
        )

    async def get_variables(self) -> str | None:
        """Fetch the variable details from the ISY to update local copy."""
        req_list = [
            [URL_VARIABLES, METHOD_GET, VAR_INTEGER],
            [URL_VARIABLES, METHOD_GET, VAR_STATE],
        ]
        req_urls = [self.compile_url(req) for req in req_list]
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(self.request(req_url)) for req_url in req_urls]
        results = [r for r in (t.result() for t in tasks) if r is not None]
        result = "".join(results)
        return result.replace('</vars><?xml version="1.0" encoding="UTF-8"?><vars>', "")

    async def get_network(self) -> str | None:
        """Fetch the list of network resources from the ISY."""
        req_url = self.compile_url([URL_NETWORK, URL_RESOURCES])
        result = await self.request(req_url, ok404=True)
        return result or None

    async def get_time(self) -> str | None:
        """Fetch the system time info from the ISY."""
        req_url = self.compile_url([URL_CLOCK])
        return await self.request(req_url)


def get_new_client_session(use_https: bool, tls_ver: TLSVer = "auto") -> aiohttp.ClientSession:
    """Create a new Client Session for Connecting."""
    if use_https:
        if not can_https(tls_ver):
            raise (ValueError("PyISY could not connect to the ISY. Check log for SSL/TLS error."))

        return aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True))

    return aiohttp.ClientSession()


_TLS_VERSION_MAP: dict[float, ssl.TLSVersion] = {
    1.1: ssl.TLSVersion.TLSv1_1,
    1.2: ssl.TLSVersion.TLSv1_2,
    1.3: ssl.TLSVersion.TLSv1_3,
}

# Floor for "auto" negotiation. Current eisy/Polisy IoX firmware rejects
# TLS <=1.1 (RFC 8996). Stock ISY-994 firmware (4.5.4+) defaults to TLS 1.2
# and is user-configurable down to 1.0/1.1; users who have manually
# downgraded their ISY-994's HTTPS Server Settings can still pin tls_ver=1.1.
_TLS_AUTO_MIN = ssl.TLSVersion.TLSv1_2


def _warn_deprecated_pin(tls_ver: float) -> None:
    """Warn callers that pinning tls_ver is deprecated."""
    warnings.warn(
        f"Passing tls_ver={tls_ver!r} is deprecated. The default 'auto' lets "
        "OpenSSL negotiate the highest TLS version both peers support "
        "(floor: TLS 1.2). Only pin tls_ver=1.1 if you have manually "
        "downgraded an ISY-994's HTTPS Server Settings below TLS 1.2.",
        DeprecationWarning,
        stacklevel=3,
    )


def get_sslcontext(
    use_https: bool,
    tls_ver: TLSVer = "auto",
    verify_ssl: bool = False,
) -> ssl.SSLContext | None:
    """Create an SSLContext object to use for the connections.

    eisy/Polisy and stock ISY-994 ship a self-signed cert, so verify_ssl
    defaults to False. Set verify_ssl=True for users who have installed a
    properly-signed certificate (CA-signed or imported via PKCS12) and have
    a CA bundle the OS trusts.
    """
    if not use_https:
        return None

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = verify_ssl
    context.verify_mode = ssl.CERT_REQUIRED if verify_ssl else ssl.CERT_NONE

    if tls_ver == "auto":
        context.minimum_version = _TLS_AUTO_MIN
    elif tls_ver in _TLS_VERSION_MAP:
        _warn_deprecated_pin(tls_ver)
        context.minimum_version = _TLS_VERSION_MAP[tls_ver]
        context.maximum_version = _TLS_VERSION_MAP[tls_ver]
    else:
        raise ValueError(f"Unsupported TLS version: {tls_ver!r}")

    # Allow older ciphers for original ISY-994 hardware (TLS 1.1/1.2 only;
    # set_ciphers does not affect TLS 1.3 ciphersuites).
    context.set_ciphers("DEFAULT:!aNULL:!eNULL:!MD5:!3DES:!DES:!RC4:!IDEA:!SEED:!aDSS:!SRP:!PSK")
    # Note: ``OP_LEGACY_SERVER_CONNECT`` (ISY-994 RFC-5746 compat) is
    # NOT set here. ``Connection.request()`` enables it on demand the
    # first time the peer rejects the handshake with
    # ``UNSAFE_LEGACY_RENEGOTIATION_DISABLED`` — that way modern peers
    # (eisy/Polisy IoX, ISY-994 firmware that honors RFC 5746) keep
    # strict TLS, and only the controllers that actually need it
    # degrade.
    return context


def can_https(tls_ver: TLSVer) -> bool:
    """
    Verify minimum requirements to use an HTTPS connection.

    Returns boolean indicating whether HTTPS is available.
    """
    output = True

    # check that Python was compiled against correct OpenSSL lib
    if "PROTOCOL_TLS_CLIENT" not in dir(ssl):
        _LOGGER.error("PyISY cannot use HTTPS: Compiled against old OpenSSL library. See docs.")
        output = False

    # check the requested TLS version
    if tls_ver != "auto" and tls_ver not in _TLS_VERSION_MAP:
        _LOGGER.error(
            "PyISY cannot use HTTPS: tls_ver must be 'auto' or one of "
            "1.1, 1.2, 1.3 (only ISY/IoX-supported versions)."
        )
        output = False

    return output
