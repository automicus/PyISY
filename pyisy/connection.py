"""Connection to the ISY."""
from __future__ import annotations

import asyncio
from dataclasses import InitVar, dataclass, field
from urllib.parse import ParseResult, quote, urlencode, urlparse

import aiohttp

from pyisy.configuration import Configuration, ConfigurationData
from pyisy.constants import URL_PING
from pyisy.exceptions import ISYConnectionError, ISYInvalidAuthError
from pyisy.helpers.session import get_new_client_session, get_sslcontext
from pyisy.logging import _LOGGER, enable_logging

MAX_HTTPS_CONNECTIONS_ISY = 2
MAX_HTTP_CONNECTIONS_ISY = 5
MAX_HTTPS_CONNECTIONS_IOX = 20
MAX_HTTP_CONNECTIONS_IOX = 50

MAX_RETRIES = 5
RETRY_BACKOFF = [0.01, 0.10, 0.25, 1, 2]  # Seconds

HTTP_OK = 200  # Valid request received, will run it
HTTP_UNAUTHORIZED = 401  # User authentication failed
HTTP_NOT_FOUND = 404  # Unrecognized request received and ignored
HTTP_SERVICE_UNAVAILABLE = 503  # Valid request received, system too busy to run it

HTTP_TIMEOUT = 30

HTTP_HEADERS = {
    "Connection": "keep-alive",
    "Keep-Alive": "5000",
    "Accept-Encoding": "gzip, deflate",
}

EMPTY_XML_RESPONSE = '<?xml version="1.0" encoding="UTF-8"?>'


@dataclass
class ISYConnectionInfo:
    """Dataclass to represent connection details."""

    url: str
    username: InitVar[str]
    password: InitVar[str]
    rest_url: str = field(init=False)
    ws_url: str = field(init=False)
    auth: aiohttp.BasicAuth = field(init=False)
    parsed_url: ParseResult = field(init=False)
    use_https: bool = field(init=False)
    websession: aiohttp.ClientSession | None = None
    tls_version: float | None = None

    def __post_init__(self, username: str, password: str) -> None:
        """Post process the connection info."""
        self.rest_url = f"{self.url.rstrip('/')}/rest"
        self.ws_url = f"{self.rest_url.replace('http', 'ws').rstrip('/')}/subscribe"
        self.auth = aiohttp.BasicAuth(username, password)
        self.parsed_url = urlparse(self.url)
        self.use_https = self.url.startswith("https")


class Connection:
    """Connection object to manage connection to and interaction with ISY."""

    connection_info: ISYConnectionInfo

    def __init__(self, connection_info: ISYConnectionInfo) -> None:
        """Initialize the Connection object."""
        if len(_LOGGER.handlers) == 0:
            enable_logging(add_null_handler=True)

        self.connection_info = connection_info

        self.semaphore = asyncio.Semaphore(
            MAX_HTTPS_CONNECTIONS_ISY
            if connection_info.use_https
            else MAX_HTTP_CONNECTIONS_ISY
        )

        if connection_info.websession is None:
            connection_info.websession = get_new_client_session(connection_info)
        self.req_session = connection_info.websession
        self.sslcontext = get_sslcontext(connection_info)

    async def test_connection(self) -> ConfigurationData:
        """Test the connection and get the config for the ISY."""
        config = Configuration()
        if not (config_data := await config.update(self)):
            raise ISYConnectionError(
                "Could not connect to the ISY with the parameters provided"
            )
        return config_data

    def increase_available_connections(self) -> None:
        """Increase the number of allowed connections for newer hardware."""
        _LOGGER.debug("Increasing available simultaneous connections")
        self.semaphore = asyncio.Semaphore(
            MAX_HTTPS_CONNECTIONS_IOX
            if self.connection_info.use_https
            else MAX_HTTP_CONNECTIONS_IOX
        )

    async def close(self) -> None:
        """Cleanup connections and prepare for exit."""
        await self.req_session.close()

    @property
    def url(self) -> str:
        """Return the full connection url."""
        return self.connection_info.url

    # COMMON UTILITIES
    def compile_url(self, path: list[str], query: dict[str, str] | None = None) -> str:
        """Compile the URL to fetch from the ISY."""
        url = f"{self.connection_info.rest_url}/{'/'.join([quote(item) for item in path])}"
        if query is not None:
            url += f"?{urlencode(query)}"
        return url

    async def request(
        self, url: str, retries: int = 0, ok404: bool = False, delay: float = 0
    ) -> str | None:
        """Execute request to ISY REST interface."""
        _LOGGER.debug("Request: %s", url)
        if delay:
            await asyncio.sleep(delay)
        try:
            async with self.semaphore, self.req_session.get(
                url,
                auth=self.connection_info.auth,
                headers=HTTP_HEADERS,
                timeout=HTTP_TIMEOUT,
                ssl=self.sslcontext,
            ) as res:
                endpoint = url.split("rest", 1)[1]
                if res.status == HTTP_OK:
                    _LOGGER.debug("Response received: %s", endpoint)
                    results = await res.text(encoding="utf-8", errors="ignore")
                    if results != EMPTY_XML_RESPONSE:
                        return results
                    _LOGGER.debug("Invalid empty XML returned: %s", endpoint)
                    res.release()
                if res.status == HTTP_NOT_FOUND:
                    if ok404:
                        _LOGGER.debug("Response received %s", endpoint)
                        res.release()
                        return ""
                    _LOGGER.error("Reported an Invalid Command received %s", endpoint)
                    res.release()
                    return None
                if res.status == HTTP_UNAUTHORIZED:
                    _LOGGER.error("Invalid credentials provided for ISY connection.")
                    res.release()
                    raise ISYInvalidAuthError(
                        "Invalid credentials provided for ISY connection."
                    )
                if res.status == HTTP_SERVICE_UNAVAILABLE:
                    _LOGGER.warning("ISY too busy to process request %s", endpoint)
                    res.release()

        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout while trying to connect to the ISY.")
        except (
            aiohttp.ClientOSError,
            aiohttp.ServerDisconnectedError,
        ):
            _LOGGER.debug("ISY not ready or closed connection.")
        except aiohttp.ClientResponseError as err:
            _LOGGER.error(
                "Client Response %s Error %s %s", err.status, err.message, endpoint
            )
        except aiohttp.ClientError as err:
            _LOGGER.error(
                "Could not receive response from device because of a network issue: %s",
                type(err),
            )

        if retries is None:
            raise ISYConnectionError()
        if retries < MAX_RETRIES:
            _LOGGER.debug(
                "Retrying ISY Request in %ss, retry %s.",
                RETRY_BACKOFF[retries],
                retries + 1,
            )
            # sleep to allow the ISY to catch up
            await asyncio.sleep(RETRY_BACKOFF[retries])
            # recurse to try again
            retry_result = await self.request(url, retries + 1, ok404=ok404)
            return retry_result
        # fail for good
        _LOGGER.error(
            "Bad ISY Request: (%s) Failed after %s retries.",
            url,
            retries,
        )
        return None

    async def ping(self) -> bool:
        """Test connection to the ISY and return True if alive."""
        req_url = self.compile_url([URL_PING])
        result = await self.request(req_url, ok404=True)
        return result is not None

    async def get_description(self) -> str | None:
        """Fetch the services description from the ISY."""
        return await self.request(f"{self.connection_info.url}/desc")
