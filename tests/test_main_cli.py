"""Smoke tests for ``python -m pyisy``.

The CLI itself isn't unit-testable (its argparse block lives under
``if __name__ == "__main__":``), but we can confirm via subprocess that
``-h`` prints expected help text and that running with no arguments fails
with a usage error and exit code 2 — matching argparse defaults."""

from __future__ import annotations

import subprocess
import sys


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pyisy", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_help_text_lists_required_arguments() -> None:
    proc = _run("-h")
    assert proc.returncode == 0
    out = proc.stdout
    # All three positional args must be documented.
    assert "url" in out
    assert "username" in out
    assert "password" in out
    # And the documented optional flags. tls_ver is no longer a CLI option:
    # the script always uses the new "auto" default and verify_ssl=False,
    # which is the correct configuration for every shipped controller.
    for flag in ("--verbose", "--no-events", "--node-servers"):
        assert flag in out, f"help missing {flag!r}"
    assert "--tls-ver" not in out, "--tls-ver should have been removed in #494"


def test_missing_args_exits_with_usage_error() -> None:
    proc = _run()
    # argparse prints usage to stderr and exits 2 when required args missing.
    assert proc.returncode == 2
    err = proc.stderr
    assert "usage:" in err.lower()
    # The first missing positional should be called out.
    assert "url" in err


def test_invalid_scheme_logged_and_returns_cleanly(tmp_path) -> None:
    """A non-http(s) URL is rejected by ``main`` (logged + returns False)
    rather than crashing. Run with a fake URL — the script should exit 0
    because ``main`` returns before attempting any network I/O."""
    proc = _run("ftp://nope", "u", "p")
    # Returns False from main → asyncio.run returns None → exit 0
    assert proc.returncode == 0
    # Error message went through the logger.
    assert "invalid" in (proc.stderr + proc.stdout).lower()
