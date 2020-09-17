"""ISY TCP Socket Event Reader."""
import errno
import select
import ssl

from ..constants import SOCKET_BUFFER_SIZE
from ..exceptions import (
    ISYInvalidAuthError,
    ISYMaxConnections,
    ISYStreamDataError,
    ISYStreamDisconnected,
)


class ISYEventReader:
    """Read in streams of ISY HTTP Events."""

    HTTP_HEADER_SEPERATOR = b"\r\n"
    HTTP_HEADER_BODY_SEPERATOR = b"\r\n\r\n"
    HTTP_HEADER_BODY_SEPERATOR_LEN = 4
    REACHED_MAX_CONNECTIONS_RESPONSE = b"HTTP/1.1 817"
    HTTP_NOT_AUTHORIZED_RESPONSE = b"HTTP/1.1 401"
    CONTENT_LENGTH_HEADER = b"content-length"
    HEADER_SEPERATOR = b":"

    def __init__(self, isy_read_socket):
        """Initialize the ISYEventStream class."""
        self._event_buffer = b""
        self._event_content_length = None
        self._event_count = 0
        self._socket = isy_read_socket

    def read_events(self, timeout):
        """Read events from the socket."""
        events = []
        # poll socket for new data
        if not self._receive_into_buffer(timeout):
            return events

        while True:
            # Read the headers if we do not have content length yet
            if not self._event_content_length:
                seperator_position = self._event_buffer.find(
                    self.HTTP_HEADER_BODY_SEPERATOR
                )
                if seperator_position == -1:
                    return events
                self._parse_headers(seperator_position)

            # If we do not have a body yet
            if len(self._event_buffer) < self._event_content_length:
                return events

            # We have the body now
            body = self._event_buffer[0 : self._event_content_length]
            self._event_count += 1
            self._event_buffer = self._event_buffer[self._event_content_length :]
            self._event_content_length = None
            events.append(body.decode(encoding="utf-8", errors="ignore"))

    def _receive_into_buffer(self, timeout):
        """Receive data on available on the socket.

        If we get an empty read on the first read attempt
        this means the isy has disconnected.

        If we get an empty read on the first read attempt
        and we have seen only one event, the isy has reached
        the maximum number of event listeners.
        """
        inready, _, _ = select.select([self._socket], [], [], timeout)
        if self._socket not in inready:
            return False

        try:
            # We have data on the wire, read as much as we can
            # up to 32 * SOCKET_BUFFER_SIZE
            for read_count in range(0, 32):
                new_data = self._socket.recv(SOCKET_BUFFER_SIZE)
                print(f"read_count: {read_count} new_data: {new_data}")
                if len(new_data) == 0:
                    if read_count != 0:
                        break
                    if self._event_count <= 1:
                        raise ISYMaxConnections(self._event_buffer)
                    raise ISYStreamDisconnected(self._event_buffer)

                self._event_buffer += new_data
        except ssl.SSLWantReadError:
            pass
        except OSError as ex:
            if ex.errno != errno.EWOULDBLOCK:
                raise

        return True

    def _parse_headers(self, seperator_position):
        """Find the content-length in the headers."""
        headers = self._event_buffer[0:seperator_position]
        if headers.startswith(self.REACHED_MAX_CONNECTIONS_RESPONSE):
            raise ISYMaxConnections(self._event_buffer)
        if headers.startswith(self.HTTP_NOT_AUTHORIZED_RESPONSE):
            raise ISYInvalidAuthError(self._event_buffer)
        self._event_buffer = self._event_buffer[
            seperator_position + self.HTTP_HEADER_BODY_SEPERATOR_LEN :
        ]
        for header in headers.split(self.HTTP_HEADER_SEPERATOR)[1:]:
            header_name, header_value = header.split(self.HEADER_SEPERATOR, 1)
            if header_name.strip().lower() != self.CONTENT_LENGTH_HEADER:
                continue
            self._event_content_length = int(header_value.strip())
        if not self._event_content_length:
            raise ISYStreamDataError(headers)
