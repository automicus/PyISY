"""Implementation of module for command line.

The module can be tested by running the following command:
`python3 -m pyisy http://your-isy-url:80 username password`
Use `python3 -m pyisy -h` for full usage information.

This script can also be copied and used as a template for
using this module.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import time
from typing import Any

from pyisy.connection import ISYConnectionError, ISYConnectionInfo, ISYInvalidAuthError
from pyisy.constants import DEFAULT_DIR, NodeChangeAction, SystemStatus
from pyisy.helpers.events import NodeChangedEvent
from pyisy.isy import ISY
from pyisy.logging import LOG_VERBOSE, enable_logging
from pyisy.util.output import write_to_file

_LOGGER = logging.getLogger(__name__)


async def main(args: argparse.Namespace) -> None:
    """Execute connection to ISY and load all system info."""
    _LOGGER.info("Starting PyISY...")
    t_0 = time.time()

    connection_info = ISYConnectionInfo(
        args.url, args.username, args.password, tls_version=args.tls_version
    )
    # Connect to ISY controller.
    isy = ISY(connection_info, use_websocket=True, args=args)

    try:
        await isy.initialize(
            nodes=args.nodes,
            clock=args.clock,
            programs=args.programs,
            variables=args.variables,
            networking=args.networking,
            node_servers=args.node_servers,
        )
    except (ISYInvalidAuthError, ISYConnectionError):
        _LOGGER.error(
            "Failed to connect to the ISY, please adjust settings and try again."
        )
        await isy.shutdown()
        return
    except Exception as err:  # pylint: disable=broad-except
        _LOGGER.error("Unknown error occurred: %s", err.args[0], exc_info=True)
        await isy.shutdown()
        return

    def node_changed_handler(event: NodeChangedEvent, key: str) -> None:
        """Handle a node changed event sent from Nodes class."""
        _LOGGER.info(
            "Node %s Changed: %s %s",
            event.address,
            NodeChangeAction(event.action).name.replace("_", " ").title(),
            event.event_info if event.event_info else "",
        )

    def system_status_handler(event: SystemStatus) -> None:
        """Handle a system status changed event sent ISY class."""
        _LOGGER.info("System Status Changed: %s", event.name.replace("_", " ").title())

    def status_handler(event: Any, key: str) -> None:
        """Handle a generic status changed event sent."""
        _LOGGER.info("%s status changed: %s", key.title(), event)

    # Print a representation of all the Nodes
    if args.nodes:
        _LOGGER.debug(repr(isy.nodes))
        if args.file:
            # Write nodes to file for debugging:
            await isy.loop.run_in_executor(
                None,
                write_to_file,
                isy.nodes.get_tree(),
                f"{DEFAULT_DIR}nodes-tree.json",
            )
            await isy.loop.run_in_executor(
                None,
                write_to_file,
                isy.nodes.to_dict(),
                f"{DEFAULT_DIR}nodes-loaded.json",
            )
        isy.nodes.status_events.subscribe(node_changed_handler, key="nodes")
    if args.programs:
        _LOGGER.debug(repr(isy.programs))
        if args.file:
            await isy.loop.run_in_executor(
                None,
                write_to_file,
                isy.programs.get_tree(),
                f"{DEFAULT_DIR}programs.json",
            )
        isy.programs.status_events.subscribe(status_handler, key="programs")
    if args.variables:
        _LOGGER.debug(repr(isy.variables))
        if args.file:
            await isy.loop.run_in_executor(
                None,
                write_to_file,
                isy.variables.to_dict(),
                f"{DEFAULT_DIR}variables.json",
            )
        isy.variables.status_events.subscribe(status_handler, key="variables")
    if args.networking:
        _LOGGER.debug(repr(isy.networking))
        if args.file:
            await isy.loop.run_in_executor(
                None,
                write_to_file,
                isy.networking.to_dict(),
                f"{DEFAULT_DIR}networking.json",
            )
    if args.node_servers:
        _LOGGER.debug(isy.node_servers)
        if args.file:
            await isy.loop.run_in_executor(
                None,
                write_to_file,
                isy.node_servers.to_dict(),
                f"{DEFAULT_DIR}node-servers.json",
            )
    if args.clock:
        _LOGGER.debug(repr(isy.clock))
    _LOGGER.info("Total Loading time: %.2fs", time.time() - t_0)

    system_status_subscriber = None

    try:
        if args.events:
            await asyncio.sleep(1)
            isy.websocket.start()
            system_status_subscriber = isy.status_events.subscribe(
                system_status_handler
            )
            while True:
                await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        if system_status_subscriber:
            system_status_subscriber.unsubscribe()
        await isy.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog=__package__,
        description="Connect and interact with an Universal Devices, Inc, ISY/IoX device.",
    )
    parser.add_argument("url", type=str)
    parser.add_argument("username", type=str)
    parser.add_argument("password", type=str)
    parser.add_argument(
        "-t",
        "--tls-ver",
        dest="tls_version",
        type=float,
        help="Set the TLS version (1.2 or 1.2) for older ISYs",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable VERBOSE logging (default is DEBUG)",
    )
    parser.add_argument(
        "-q",
        "--no-events",
        dest="events",
        action="store_false",
        help="Disable the event stream",
    )
    parser.add_argument(
        "-n", "--no-nodes", dest="nodes", action="store_false", help="Do not load Nodes"
    )
    parser.add_argument(
        "-c",
        "--no-clock",
        dest="clock",
        action="store_false",
        help="Do not load Clock Info",
    )
    parser.add_argument(
        "-p",
        "--no-programs",
        dest="programs",
        action="store_false",
        help="Do not load Programs",
    )
    parser.add_argument(
        "-i",
        "--no-variables",
        dest="variables",
        action="store_false",
        help="Do not load Variables",
    )
    parser.add_argument(
        "-w",
        "--no-network",
        dest="networking",
        action="store_false",
        help="Do not load Network Resources",
    )
    parser.add_argument(
        "-s",
        "--node-servers",
        dest="node_servers",
        action="store_false",
        help="Do not load Node Server Definitions",
    )
    parser.add_argument(
        "-o",
        "--file",
        dest="file",
        action="store_true",
        help="Dump tree information to file",
    )
    parser.set_defaults(use_https=False, tls_version=None, verbose=False)
    command_line_args: argparse.Namespace = parser.parse_args()

    enable_logging(LOG_VERBOSE if command_line_args.verbose else logging.DEBUG)

    _LOGGER.info(
        "ISY URL: %s, username: %s",
        command_line_args.url,
        command_line_args.username,
    )

    try:
        asyncio.run(main(command_line_args))
    except KeyboardInterrupt:
        _LOGGER.warning("KeyboardInterrupt received. Disconnecting!")
