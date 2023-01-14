"""Logging helper functions."""

import logging

_LOGGER = logging.getLogger(__package__)
LOG_LEVEL = logging.DEBUG
LOG_VERBOSE = 5
LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def enable_logging(
    level=LOG_LEVEL,
    add_null_handler: bool = False,
    log_no_color: bool = False,
) -> None:
    """Set up the logging."""
    # Adapted from home-assistant/core/homeassistant/bootstrap.py
    if not log_no_color and not add_null_handler:
        try:
            # pylint: disable=import-outside-toplevel
            from colorlog import ColoredFormatter

            # basicConfig must be called after importing colorlog in order to
            # ensure that the handlers it sets up wraps the correct streams.
            logging.basicConfig(level=level)
            logging.addLevelName(LOG_VERBOSE, "VERBOSE")

            colorfmt = f"%(log_color)s{LOG_FORMAT}%(reset)s"
            logging.getLogger().handlers[0].setFormatter(
                ColoredFormatter(
                    colorfmt,
                    datefmt=LOG_DATE_FORMAT,
                    reset=True,
                    log_colors={
                        "VERBOSE": "blue",
                        "DEBUG": "cyan",
                        "INFO": "green",
                        "WARNING": "yellow",
                        "ERROR": "red",
                        "CRITICAL": "red",
                    },
                )
            )
        except ImportError:
            pass

    # If the above initialization failed for any reason, setup the default
    # formatting.  If the above succeeds, this will result in a no-op.
    logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT, level=level)

    if add_null_handler:
        _LOGGER.addHandler(logging.NullHandler())

    # Suppress overly verbose logs from libraries that aren't helpful
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
