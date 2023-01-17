"""ISY Websession and SSL Helper Functions."""
from __future__ import annotations

import ssl
import sys
from typing import TYPE_CHECKING

import aiohttp

from pyisy.logging import _LOGGER

if TYPE_CHECKING:
    from pyisy.connection import ISYConnectionInfo


def get_new_client_session(conn_info: ISYConnectionInfo) -> aiohttp.ClientSession:
    """Create a new Client Session for Connecting."""
    if conn_info.use_https:
        if not can_https(conn_info.tls_version):
            raise (
                ValueError(
                    "PyISY could not connect to the ISY. "
                    "Check log for SSL/TLS error."
                )
            )
        return aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True))
    return aiohttp.ClientSession()


def get_sslcontext(conn_info: ISYConnectionInfo) -> ssl.SSLContext | None:
    """Create an SSLContext object to use for the connections."""
    if not conn_info.use_https:
        return None
    if conn_info.tls_version is None:
        # Auto-negotiate TLS Version (non-ISY994 models only)
        return ssl.SSLContext(ssl.PROTOCOL_TLS)
    if conn_info.tls_version == 1.1:
        context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_1)
    elif conn_info.tls_version == 1.2:
        context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)

    # Allow older ciphers for older ISYs
    context.set_ciphers(
        "DEFAULT:!aNULL:!eNULL:!MD5:!3DES:!DES:!RC4:!IDEA:!SEED:!aDSS:!SRP:!PSK"
    )
    return context


def can_https(tls_ver: float | None) -> bool:
    """
    Verify minimum requirements to use an HTTPS connection.

    Returns boolean indicating whether HTTPS is available.
    """
    output = True

    # check python version
    if sys.version_info < (3, 7):
        _LOGGER.error("PyISY cannot use HTTPS: Invalid Python version. See docs.")
        output = False

    # check that Python was compiled against correct OpenSSL lib
    if "PROTOCOL_TLSv1_1" not in dir(ssl):
        _LOGGER.error(
            "PyISY cannot use HTTPS: Compiled against old OpenSSL library. See docs."
        )
        output = False

    # check the requested TLS version
    if tls_ver is not None and tls_ver not in [1.1, 1.2]:
        _LOGGER.error(
            "PyISY cannot use HTTPS: Only TLS 1.1 and 1.2 are supported by the ISY994i controller."
            " Set tls_version=None for newer models."
        )
        output = False

    return output
