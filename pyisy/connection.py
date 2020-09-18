"""Connection to the ISY."""
import asyncio
import logging
import ssl
import sys
from urllib.parse import quote, urlencode

import aiohttp

from .constants import (
    _LOGGER,
    LOG_DATE_FORMAT,
    LOG_FORMAT,
    LOG_LEVEL,
    METHOD_GET,
    URL_CLOCK,
    URL_CONFIG,
    URL_DEFINITIONS,
    URL_MEMBERS,
    URL_NETWORK,
    URL_NODES,
    URL_PING,
    URL_PROGRAMS,
    URL_RESOURCES,
    URL_STATUS,
    URL_SUBFOLDERS,
    URL_VARIABLES,
    VAR_INTEGER,
    VAR_STATE,
    XML_FALSE,
    XML_TRUE,
)
from .exceptions import ISYConnectionError, ISYInvalidAuthError

MAX_RETRIES = 5
MAX_HTTPS_CONNECTIONS = 2
MAX_HTTP_CONNECTIONS = 5
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


class Connection:
    """Connection object to manage connection to and interaction with ISY."""

    def __init__(
        self,
        address,
        port,
        username,
        password,
        use_https=False,
        tls_ver=1.1,
        webroot="",
        websession=None,
    ):
        """Initialize the Connection object."""
        if not len(_LOGGER.handlers):
            logging.basicConfig(
                format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT, level=LOG_LEVEL
            )
            _LOGGER.addHandler(logging.NullHandler())
            logging.getLogger("urllib3").setLevel(logging.WARNING)

        self._address = address
        self._port = port
        self._username = username
        self._password = password
        self._auth = aiohttp.BasicAuth(self._username, self._password)
        self._webroot = webroot.rstrip("/")
        self.req_session = websession
        self._tls_ver = tls_ver
        self.use_https = use_https

        self.semaphore = asyncio.Semaphore(
            MAX_HTTPS_CONNECTIONS if use_https else MAX_HTTP_CONNECTIONS
        )

        if websession is None:
            websession = get_new_client_session(use_https, tls_ver)
        self.req_session = websession
        self.sslcontext = get_sslcontext(use_https, tls_ver)

    async def test_connection(self):
        """Test the connection and get the config for the ISY."""
        config = await self.get_config(retries=None)
        if not config:
            _LOGGER.error("Could not connect to the ISY with the parameters provided.")
            raise ISYConnectionError()
        return config

    async def close(self):
        """Cleanup connections and prepare for exit."""
        await self.req_session.close()

    @property
    def connection_info(self):
        """Return the connection info required to connect to the ISY."""
        connection_info = {}
        connection_info["auth"] = self._auth.encode()
        connection_info["addr"] = self._address
        connection_info["port"] = int(self._port)
        connection_info["passwd"] = self._password
        connection_info["webroot"] = self._webroot
        if self.use_https and self._tls_ver:
            connection_info["tls"] = self._tls_ver

        return connection_info

    # COMMON UTILITIES
    def compile_url(self, path, query=None):
        """Compile the URL to fetch from the ISY."""
        url = "https://" if self.use_https else "http://"
        url += f"{self._address}:{self._port}{self._webroot}"
        if path is not None:
            url += "/rest/" + "/".join([quote(item) for item in path])

        if query is not None:
            url += "?" + urlencode(query)

        return url

    async def request(self, url, retries=0, ok404=False, delay=0):
        """Execute request to ISY REST interface."""
        _LOGGER.debug("ISY Request: %s", url)
        if delay:
            await asyncio.sleep(delay)
        try:
            async with self.semaphore, self.req_session.get(
                url,
                auth=self._auth,
                headers=HTTP_HEADERS,
                timeout=HTTP_TIMEOUT,
                ssl=self.sslcontext,
            ) as res:
                if res.status == HTTP_OK:
                    _LOGGER.debug("ISY Response Received.")
                    results = await res.text(encoding="utf-8", errors="ignore")
                    return results
                if res.status == HTTP_NOT_FOUND:
                    if ok404:
                        _LOGGER.debug("ISY Response Received.")
                        res.release()
                        return ""
                    _LOGGER.error("ISY Reported an Invalid Command Received.")
                    res.release()
                    return None
                if res.status == HTTP_UNAUTHORIZED:
                    _LOGGER.error("Invalid credentials provided for ISY connection.")
                    res.release()
                    raise ISYInvalidAuthError(
                        "Invalid credentials provided for ISY connection."
                    )
                if res.status == HTTP_SERVICE_UNAVAILABLE:
                    _LOGGER.warning("ISY too busy to process request.")
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
                "Client Response Error from ISY: %s %s.", err.status, err.message
            )
        except aiohttp.ClientError as err:
            _LOGGER.error(
                "ISY Could not receive response from device because of a network issue: %s",
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
            retry_result = await self.request(url, retries + 1, ok404=False)
            return retry_result
        # fail for good
        _LOGGER.error(
            "Bad ISY Request: %s %s: Failed after %s retries.",
            url,
            res.status,
            retries,
        )
        return None

    async def ping(self):
        """Test connection to the ISY and return True if alive."""
        req_url = self.compile_url([URL_PING])
        result = await self.request(req_url, ok404=True)
        return result is not None

    async def get_description(self):
        """Fetch the services description from the ISY."""
        url = "https://" if self.use_https else "http://"
        url += f"{self._address}:{self._port}{self._webroot}/desc"
        result = await self.request(url)
        return result

    async def get_config(self, retries=0):
        """Fetch the configuration from the ISY."""
        req_url = self.compile_url([URL_CONFIG])
        result = await self.request(req_url, retries=retries)
        return result

    async def get_programs(self, address=None):
        """Fetch the list of programs from the ISY."""
        addr = [URL_PROGRAMS]
        if address is not None:
            addr.append(str(address))
        req_url = self.compile_url(addr, {URL_SUBFOLDERS: XML_TRUE})
        result = await self.request(req_url)
        return result

    async def get_nodes(self):
        """Fetch the list of nodes/groups/scenes from the ISY."""
        req_url = self.compile_url([URL_NODES], {URL_MEMBERS: XML_FALSE})
        result = await self.request(req_url)
        return result

    async def get_status(self):
        """Fetch the status of nodes/groups/scenes from the ISY."""
        req_url = self.compile_url([URL_STATUS])
        result = await self.request(req_url)
        return result

    async def get_variable_defs(self):
        """Fetch the list of variables from the ISY."""
        req_list = [
            [URL_VARIABLES, URL_DEFINITIONS, VAR_INTEGER],
            [URL_VARIABLES, URL_DEFINITIONS, VAR_STATE],
        ]
        req_urls = [self.compile_url(req) for req in req_list]
        results = await asyncio.gather(
            *[self.request(req_url) for req_url in req_urls], return_exceptions=True
        )
        return results

    async def get_variables(self):
        """Fetch the variable details from the ISY to update local copy."""
        req_list = [
            [URL_VARIABLES, METHOD_GET, VAR_INTEGER],
            [URL_VARIABLES, METHOD_GET, VAR_STATE],
        ]
        req_urls = [self.compile_url(req) for req in req_list]
        results = await asyncio.gather(
            *[self.request(req_url) for req_url in req_urls], return_exceptions=True
        )
        results = [r for r in results if r is not None]  # Strip any bad requests.
        result = "".join(results)
        result = result.replace(
            '</vars><?xml version="1.0" encoding="UTF-8"?><vars>', ""
        )
        return result

    async def get_network(self):
        """Fetch the list of network resources from the ISY."""
        req_url = self.compile_url([URL_NETWORK, URL_RESOURCES])
        result = await self.request(req_url)
        return result

    async def get_time(self):
        """Fetch the system time info from the ISY."""
        req_url = self.compile_url([URL_CLOCK])
        result = await self.request(req_url)
        return result


def get_new_client_session(use_https, tls_ver=1.1):
    """Create a new Client Session for Connecting."""
    if use_https:
        if not can_https(tls_ver):
            raise (
                ValueError(
                    "PyISY could not connect to the ISY. "
                    "Check log for SSL/TLS error."
                )
            )

        return aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True))

    return aiohttp.ClientSession()


def get_sslcontext(use_https, tls_ver=1.1):
    """Create an SSLContext object to use for the connections."""
    if not use_https:
        return None
    if tls_ver == 1.1:
        return ssl.SSLContext(ssl.PROTOCOL_TLSv1_1)
    elif tls_ver == 1.2:
        return ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)


def can_https(tls_ver):
    """
    Verify minimum requirements to use an HTTPS connection.

    Returns boolean indicating whether HTTPS is available.
    """
    output = True

    # check python version
    if sys.version_info < (3, 7):
        _LOGGER.error("PyISY cannot use HTTPS: Invalid Python version. See docs.")
        output = False

    # check that Python was compiled against correct OpenSSL lib
    if "PROTOCOL_TLSv1_1" not in dir(ssl):
        _LOGGER.error(
            "PyISY cannot use HTTPS: Compiled against old OpenSSL "
            + "library. See docs."
        )
        output = False

    # check the requested TLS version
    if tls_ver not in [1.1, 1.2]:
        _LOGGER.error(
            "PyISY cannot use HTTPS: Only TLS 1.1 and 1.2 are supported "
            + "by the ISY controller."
        )
        output = False

    return output
