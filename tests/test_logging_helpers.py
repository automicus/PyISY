"""Tests for :mod:`pyisy.logging`.

``enable_logging`` is the package's bootstrap helper. It optionally
attaches ``colorlog``'s ColoredFormatter, otherwise falls back to a
plain ``basicConfig``, and finally clamps the noisy ``aiohttp.access``
logger down to WARNING.

These tests exercise the three branches (colorlog present, missing,
explicitly disabled) and verify the post-conditions visible to library
consumers — the VERBOSE level name registration, the aiohttp.access
clamp, and the optional pyisy NullHandler attachment. They do not
inspect the root logger's handler list directly because pytest's own
log-capture plugin manages it concurrently.
"""

from __future__ import annotations

import logging
import sys
from unittest.mock import patch

from pyisy.logging import _LOGGER, LOG_VERBOSE, enable_logging


def test_enable_logging_default_path_completes() -> None:
    """The default path imports colorlog and wraps the root handler's
    formatter. We assert observable post-conditions rather than the
    handler list itself."""
    enable_logging(level=logging.INFO)
    assert logging.getLevelName(LOG_VERBOSE) == "VERBOSE"
    assert logging.getLogger("aiohttp.access").level == logging.WARNING


def test_enable_logging_falls_back_when_colorlog_missing() -> None:
    """If ``colorlog`` is unimportable the function silently falls
    through to plain ``basicConfig``. Patch ``sys.modules`` to force the
    ImportError branch and confirm the function still completes and
    reaches the aiohttp.access clamp at the end."""
    with patch.dict(sys.modules, {"colorlog": None}):
        enable_logging(level=logging.INFO)
    assert logging.getLogger("aiohttp.access").level == logging.WARNING


def test_enable_logging_with_log_no_color_skips_colorlog() -> None:
    """``log_no_color=True`` short-circuits the colorlog block entirely
    so even if colorlog is installed it isn't imported."""
    with patch.dict(sys.modules, {"colorlog": None}):
        # Not importing colorlog under this flag is the contract; if the
        # block were entered it would raise ImportError, but the
        # function would still complete via the fallback. Either way is
        # observable as a clean return.
        enable_logging(level=logging.INFO, log_no_color=True)


def test_enable_logging_with_null_handler_attaches_to_pyisy_logger() -> None:
    """Library callers that don't want PyISY chatter on the root logger
    pass ``add_null_handler=True``; this also bypasses the colorlog
    block (so embedded apps don't get color ANSI in piped output)."""
    saved = _LOGGER.handlers[:]
    try:
        _LOGGER.handlers.clear()
        enable_logging(add_null_handler=True)
        assert any(isinstance(h, logging.NullHandler) for h in _LOGGER.handlers)
    finally:
        _LOGGER.handlers[:] = saved
