#!/usr/bin/env python

"""A simple pyisy test template."""
import logging
import sys
from time import sleep

from pyisy import ISY
from pyisy.connection import Connection

# CONFIGURATION OPTIONS:
ADDRESS = "my.isy.io"  # IP address or hostname of your ISY
PORT = 443  # Port number to use for connection
USERNAME = "admin"  # Your username, e-mail for ISY portal
PASSWORD = "somereallygoodpassword"  # Password
USE_HTTPS = True  # True for HTTPS, False for HTTP
TLS_VER = 1.1  # TLS Version: 1.1 or 1.2, 0 for HTTP
WEBROOT = ""  # Optional, for Advanced ISY Portal use

LOG_LEVEL = logging.DEBUG
# LOG_LEVEL = 5  # (Verbose) Use this level for printing event stream socket messages
LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_LOGGER = logging.getLogger(__name__)


def main(arguments):
    """Execute primary loop."""
    logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT, level=LOG_LEVEL)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # Test the connection to ISY controller.
    try:
        Connection(
            address=ADDRESS,
            port=PORT,
            username=USERNAME,
            password=PASSWORD,
            use_https=USE_HTTPS,
            tls_ver=TLS_VER,
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
        webroot=WEBROOT,
    )

    _LOGGER.info("ISY connected: %s", isy.connected)

    if not isy.connected:
        _LOGGER.error(
            "Failed to connect to the ISY, please adjust settings and try again."
        )
        return
    # Print a representation of all the Nodes
    _LOGGER.debug(repr(isy.nodes))

    # Get the rest of the detailed status information from the ISY
    # not originally reported. This includes statuses for all NodeServer nodes.
    isy.nodes.update()

    # Connect to the Event Stream and print events in the Debug Log.
    isy.auto_update = True

    try:
        while True:
            sleep(10)
    except KeyboardInterrupt:
        _LOGGER.warning("KeyboardInterrupt received. Disconnecting!")
        if isy.connected and isy.auto_update:
            isy.auto_update = False


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
