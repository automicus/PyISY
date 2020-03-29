#!/usr/bin/env python

"""A simple pyisy test template."""
import logging
import sys
from time import sleep

from pyisy import ISY
from pyisy.connection import Connection

_LOGGER = logging.getLogger(__name__)

# CONFIGURATION OPTIONS:
ADDRESS = "my.isy.io"  # IP address or hostname of your ISY
PORT = 443  # Port number to use for connection
USERNAME = "admin"  # Your username, e-mail for ISY portal
PASSWORD = "somereallygoodpassword"  # Password
USE_HTTPS = True  # True for HTTPS, False for HTTP
TLS_VER = 1.1  # TLS Version: 1.1 or 1.2, 0 for HTTP
WEBROOT = ""  # Optional, for Advanced ISY Portal use


def main(arguments):
    """Execute primary loop."""
    fmt = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    logging.basicConfig(format=fmt, datefmt=datefmt, level=logging.DEBUG)

    # Test the connection to ISY controller.
    try:
        Connection(
            address=ADDRESS,
            port=PORT,
            username=USERNAME,
            password=PASSWORD,
            use_https=USE_HTTPS,
            tls_ver=TLS_VER,
            log=_LOGGER,
            webroot=WEBROOT,
        )
    except ValueError as err:
        _LOGGER.error(
            "Failed to connect to the ISY, "
            "please adjust settings and try again. Error: \n%s",
            err.args[0],
        )
        return

    _LOGGER.info("ISY connected! Connection properties valid, continuing.")

    # Actually connect to the ISY and download full configuration.
    isy = ISY(
        address=ADDRESS,
        port=PORT,
        username=USERNAME,
        password=PASSWORD,
        use_https=USE_HTTPS,
        tls_ver=TLS_VER,
        log=_LOGGER,
        webroot=WEBROOT,
    )

    _LOGGER.info("ISY connected: %s", isy.connected)

    # Print a representation of all the Nodes
    _LOGGER.debug(repr(isy.nodes))

    if isy.connected:
        # Connect to the Event Stream and print events in the Debug Log.
        isy.auto_update = True
    else:
        _LOGGER.error(
            "Failed to connect to the ISY, please adjust settings and try again."
        )
        return

    try:
        while True:
            sleep(10)
    except KeyboardInterrupt:
        _LOGGER.warning("KeyboardInterrupt received. Disconnecting!")
        if isy.connected and isy.auto_update:
            isy.auto_update = False


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
