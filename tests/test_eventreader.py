"""Tests for :mod:`pyisy.events.eventreader`.

The reader speaks raw HTTP-ish frames over a TCP socket — content-length
prefixed bodies separated by ``\\r\\n\\r\\n`` headers. The tests below
fake the socket with an iterable of scripted ``recv`` returns and patch
``select.select`` to claim the socket is always ready, so we exercise
the buffer/parse state machine without any real I/O.
"""

from __future__ import annotations

import errno
import ssl
from unittest.mock import patch

import pytest

from pyisy.events.eventreader import ISYEventReader
from pyisy.exceptions import (
    ISYInvalidAuthError,
    ISYMaxConnections,
    ISYStreamDataError,
    ISYStreamDisconnected,
)


class FakeSocket:
    """Plays back a scripted sequence of ``recv`` returns.

    Items in ``chunks`` may be ``bytes`` (returned verbatim) or an
    ``Exception`` instance (raised when reached). The first iteration
    drains the script; subsequent calls return ``b""`` to model a
    closed peer."""

    def __init__(self, chunks):
        self._chunks = list(chunks)

    def recv(self, _size: int) -> bytes:
        if not self._chunks:
            return b""
        item = self._chunks.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _frame(body: bytes) -> bytes:
    return b"POST /eventfeed HTTP/1.1\r\nContent-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body


@pytest.fixture
def patched_select():
    """Patch ``select.select`` so the socket is always reported ready."""
    with patch("pyisy.events.eventreader.select.select") as sel:
        sel.side_effect = lambda rs, _w, _x, _t: (rs, [], [])
        yield sel


def test_read_events_returns_decoded_body(patched_select) -> None:
    sock = FakeSocket([_frame(b"<Event>hello</Event>")])
    reader = ISYEventReader(sock)
    events = reader.read_events(timeout=0)
    assert events == ["<Event>hello</Event>"]


def test_read_events_handles_two_events_in_one_buffer(patched_select) -> None:
    """Two well-formed frames concatenated in a single ``recv`` are
    parsed as two separate events; the inter-event state must reset
    cleanly."""
    payload = _frame(b"<E>1</E>") + _frame(b"<E>2</E>")
    sock = FakeSocket([payload])
    reader = ISYEventReader(sock)
    assert reader.read_events(timeout=0) == ["<E>1</E>", "<E>2</E>"]


def test_read_events_resumes_when_body_split_across_recvs(patched_select) -> None:
    """The reader returns ``[]`` while the body is still incomplete;
    a follow-up call resumes the same parse and yields the event."""
    body = b"<Event>partial</Event>"
    frame = _frame(body)
    # SSLWantReadError between the two halves makes the inner read loop
    # exit after the first chunk so the body is still incomplete when
    # the first read_events() call returns.
    sock = FakeSocket([frame[:30], ssl.SSLWantReadError(), frame[30:]])
    reader = ISYEventReader(sock)
    assert reader.read_events(timeout=0) == []
    assert reader.read_events(timeout=0) == ["<Event>partial</Event>"]


def test_read_events_returns_empty_when_select_times_out() -> None:
    sock = FakeSocket([_frame(b"<x/>")])
    reader = ISYEventReader(sock)
    with patch("pyisy.events.eventreader.select.select", return_value=([], [], [])):
        assert reader.read_events(timeout=0) == []


def test_read_events_returns_empty_when_headers_incomplete(patched_select) -> None:
    """Without the ``\\r\\n\\r\\n`` header/body separator the reader
    bails and waits for more data."""
    sock = FakeSocket([b"POST /eventfeed HTTP/1.1\r\nContent-Length: 4\r\n"])
    reader = ISYEventReader(sock)
    assert reader.read_events(timeout=0) == []


def test_read_events_max_connections_response_raises(patched_select) -> None:
    """``HTTP/1.1 817`` is the ISY's "too many event subscribers"
    response."""
    sock = FakeSocket([b"HTTP/1.1 817 Too Many\r\n\r\n"])
    reader = ISYEventReader(sock)
    with pytest.raises(ISYMaxConnections):
        reader.read_events(timeout=0)


def test_read_events_unauthorized_response_raises(patched_select) -> None:
    sock = FakeSocket([b"HTTP/1.1 401 Unauthorized\r\n\r\n"])
    reader = ISYEventReader(sock)
    with pytest.raises(ISYInvalidAuthError):
        reader.read_events(timeout=0)


def test_read_events_missing_content_length_raises(patched_select) -> None:
    """Headers terminate but no Content-Length was advertised."""
    sock = FakeSocket([b"POST /eventfeed HTTP/1.1\r\nX-Other: 1\r\n\r\n"])
    reader = ISYEventReader(sock)
    with pytest.raises(ISYStreamDataError):
        reader.read_events(timeout=0)


def test_read_events_empty_recv_first_call_signals_max_connections(patched_select) -> None:
    """An empty first ``recv`` with ``event_count <= 1`` is the ISY
    cutting us off because we hit the connection ceiling — distinct
    from a clean disconnect later."""
    sock = FakeSocket([b""])
    reader = ISYEventReader(sock)
    with pytest.raises(ISYMaxConnections):
        reader.read_events(timeout=0)


def test_read_events_empty_recv_after_events_signals_disconnect(patched_select) -> None:
    sock = FakeSocket([b""])
    reader = ISYEventReader(sock)
    reader._event_count = 5  # simulate a healthy session that just ended
    with pytest.raises(ISYStreamDisconnected):
        reader.read_events(timeout=0)


def test_read_events_swallows_ssl_want_read(patched_select) -> None:
    """``SSLWantReadError`` is the non-blocking-SSL "try again later"
    signal; the reader treats it as no-data and returns whatever it has
    so far (here: nothing parseable yet)."""
    sock = FakeSocket([ssl.SSLWantReadError()])
    reader = ISYEventReader(sock)
    assert reader.read_events(timeout=0) == []


def test_read_events_swallows_ewouldblock(patched_select) -> None:
    sock = FakeSocket([OSError(errno.EWOULDBLOCK, "would block")])
    reader = ISYEventReader(sock)
    assert reader.read_events(timeout=0) == []


def test_read_events_propagates_other_oserror(patched_select) -> None:
    sock = FakeSocket([OSError(errno.ECONNRESET, "reset")])
    reader = ISYEventReader(sock)
    with pytest.raises(OSError):
        reader.read_events(timeout=0)
