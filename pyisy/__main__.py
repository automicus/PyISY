"""Implementation of module for command line.

The module can be tested by running the following command:
`python3 -m pyisy http://your-isy-url:80 username password`
Use `python3 -m pyisy -h` for full usage information.
"""

import argparse
import asyncio
import logging
import ssl
import time
from urllib.parse import urlparse

import aiohttp

from . import ISY
from .connection import ISYConnectionError, ISYInvalidAuthError
from .constants import LOG_DATE_FORMAT, LOG_FORMAT, LOG_VERBOSE

_LOGGER = logging.getLogger(__name__)


async def main(url, username, password, tls_ver):
    """Execute connection to ISY and load all system info."""
    _LOGGER.info("Starting PyISY...")
    t0 = time.time()
    host = urlparse(url)
    if host.scheme == "http":
        https = False
        port = host.port or 80
        websession = aiohttp.ClientSession()
        sslcontext = None
    elif host.scheme == "https":
        https = True
        port = host.port or 443
        if tls_ver == 1.1:
            sslcontext = ssl.SSLContext(ssl.PROTOCOL_TLSv1_1)
        elif tls_ver == 1.2:
            sslcontext = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
        websession = aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True),)
    else:
        _LOGGER.error("host value in configuration is invalid.")
        return False

    # Connect to ISY controller.
    isy = ISY(
        host.hostname,
        port,
        username=username,
        password=password,
        use_https=https,
        tls_ver=tls_ver,
        webroot=host.path,
        websession=websession,
        sslcontext=sslcontext,
    )

    try:
        await isy.initialize()
    except (ISYInvalidAuthError, ISYConnectionError):
        _LOGGER.error(
            "Failed to connect to the ISY, please adjust settings and try again."
        )
        await isy.shutdown()
        return
    except Exception as err:
        _LOGGER.error("Unknown error occurred: %s", err.args[0])
        await isy.shutdown()
        raise

    # Print a representation of all the Nodes
    _LOGGER.debug(repr(isy.nodes))
    _LOGGER.info("Loading time: %.2fs", time.time() - t0)
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        await isy.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog=__package__)
    parser.add_argument("url", type=str)
    parser.add_argument("username", type=str)
    parser.add_argument("password", type=str)
    parser.add_argument("-t", "--tls-ver", dest="tls_ver")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.set_defaults(use_https=False, tls_ver=1.1, verbose=False)
    args = parser.parse_args()

    loglevel = logging.DEBUG
    if args.verbose:
        loglevel = LOG_VERBOSE

    logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT, level=loglevel)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    _LOGGER.info(
        f"ISY URL: {args.url}, username: {args.username}, password: {args.password}, "
        f"TLS Version: {args.tls_ver}"
    )

    try:
        asyncio.run(
            main(
                url=args.url,
                username=args.username,
                password=args.password,
                tls_ver=args.tls_ver,
            )
        )
    except KeyboardInterrupt:
        _LOGGER.warning("KeyboardInterrupt received. Disconnecting!")
