"""Implementation of module for command line.

The module can be tested by running the following command:
`python3 -m pyisy http://your-isy-url:80 username password`
Use `python3 -m pyisy -h` for full usage information.

This script can also be copied and used as a template for
using this module.
"""

import argparse
import asyncio
import logging
import time

from pyisy.connection import ISYConnectionError, ISYConnectionInfo, ISYInvalidAuthError
from pyisy.constants import NODE_CHANGED_ACTIONS, SYSTEM_STATUS
from pyisy.isy import ISY
from pyisy.logging import LOG_VERBOSE, enable_logging
from pyisy.nodes import NodeChangedEvent

_LOGGER = logging.getLogger(__name__)


async def main(url, username, password, tls_version, events, node_servers):
    """Execute connection to ISY and load all system info."""
    _LOGGER.info("Starting PyISY...")
    t_0 = time.time()

    connection_info = ISYConnectionInfo(
        url, username, password, tls_version=tls_version
    )
    # Connect to ISY controller.
    isy = ISY(
        connection_info,
        use_websocket=True,
    )

    try:
        # await isy.initialize(node_servers) TODO: revert
        await isy.initialize(
            nodes=False,
            clock=True,
            programs=False,
            variables=False,
            networking=True,
            node_servers=False,
        )
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
    _LOGGER.info("Total Loading time: %.2fs", time.time() - t_0)

    node_changed_subscriber = None
    system_status_subscriber = None

    def node_changed_handler(event: NodeChangedEvent) -> None:
        """Handle a node changed event sent from Nodes class."""
        (event_desc, _) = NODE_CHANGED_ACTIONS[event.action]
        _LOGGER.info(
            "Subscriber--Node %s Changed: %s %s",
            event.address,
            event_desc,
            event.event_info if event.event_info else "",
        )

    def system_status_handler(event: str) -> None:
        """Handle a system status changed event sent ISY class."""
        _LOGGER.info("System Status Changed: %s", SYSTEM_STATUS.get(event))

    try:
        if events:
            isy.websocket.start()
            node_changed_subscriber = isy.nodes.status_events.subscribe(
                node_changed_handler
            )
            system_status_subscriber = isy.status_events.subscribe(
                system_status_handler
            )
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        if node_changed_subscriber:
            node_changed_subscriber.unsubscribe()
        if system_status_subscriber:
            system_status_subscriber.unsubscribe()
        await isy.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog=__package__)
    parser.add_argument("url", type=str)
    parser.add_argument("username", type=str)
    parser.add_argument("password", type=str)
    parser.add_argument("-t", "--tls-ver", dest="tls_version", type=float)
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-q", "--no-events", dest="no_events", action="store_true")
    parser.add_argument(
        "-n", "--node-servers", dest="node_servers", action="store_true"
    )
    parser.set_defaults(use_https=False, tls_version=1.2, verbose=False)
    args = parser.parse_args()

    enable_logging(LOG_VERBOSE if args.verbose else logging.DEBUG)

    _LOGGER.info(
        "ISY URL: %s, username: %s, TLS: %s",
        args.url,
        args.username,
        args.tls_version,
    )

    try:
        asyncio.run(
            main(
                url=args.url,
                username=args.username,
                password=args.password,
                tls_version=args.tls_version,
                events=(not args.no_events),
                node_servers=args.node_servers,
            )
        )
    except KeyboardInterrupt:
        _LOGGER.warning("KeyboardInterrupt received. Disconnecting!")
