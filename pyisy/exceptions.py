"""Exceptions used by the PyISY module."""
from xml.parsers.expat import ExpatError

XML_ERRORS = (AttributeError, KeyError, ValueError, TypeError, IndexError, ExpatError)
XML_PARSE_ERROR = "ISY Could not parse response, poorly formatted XML."


class ISYInvalidAuthError(Exception):
    """Invalid authorization credentials provided."""


class ISYConnectionError(Exception):
    """Invalid connection parameters provided."""


class ISYResponseParseError(Exception):
    """Error parsing a response provided by the ISY."""


class ISYStreamDataError(Exception):
    """Invalid data in the isy event stream."""


class ISYStreamDisconnected(ISYStreamDataError):
    """The isy has disconnected."""


class ISYMaxConnections(ISYStreamDisconnected):
    """The isy has disconnected because it reached maximum connections."""
