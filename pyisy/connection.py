"""Connection to the ISY."""
import base64
import logging
import ssl
import sys
import time
from urllib.parse import quote, urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning
from urllib3.poolmanager import PoolManager

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

MAX_RETRIES = 5


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
        self._webroot = webroot.rstrip("/")

        self.req_session = requests.Session()

        # setup proper HTTPS handling for the ISY
        if use_https:
            if can_https(tls_ver):
                self.use_https = True
                self._tls_ver = tls_ver
                # Most SSL certs will not be valid. Let's not warn about them.
                disable_warnings(InsecureRequestWarning)

                # ISY uses TLS1 and not SSL
                self.req_session.mount(self.compile_url(None), TLSHttpAdapter(tls_ver))
            else:
                raise (
                    ValueError(
                        "PyISY could not connect to the ISY. "
                        "Check log for SSL/TLS error."
                    )
                )
        else:
            self.use_https = False
            self._tls_ver = None

        # test settings
        if not self.ping():
            raise (
                ValueError(
                    "PyISY could not connect to the ISY "
                    "controller with the provided attributes."
                )
            )

    @property
    def connection_info(self):
        """Return the connection info required to connect to the ISY."""
        connection_info = {}
        authstr = bytes(f"{self._username}:{self._password}", "ascii")
        connection_info["auth"] = base64.encodebytes(authstr).strip().decode("ascii")
        connection_info["addr"] = self._address
        connection_info["port"] = int(self._port)
        connection_info["passwd"] = self._password
        connection_info["webroot"] = self._webroot
        if self._tls_ver:
            connection_info["tls"] = self._tls_ver

        return connection_info

    # COMMON UTILITIES
    def compile_url(self, path, query=None):
        """Compile the URL to fetch from the ISY."""
        if self.use_https:
            url = "https://"
        else:
            url = "http://"

        url += f"{self._address}:{self._port}{self._webroot}"
        if path is not None:
            url += "/rest/" + "/".join([quote(item) for item in path])

        if query is not None:
            url += "?" + urlencode(query)

        return url

    def request(self, url, retries=0, ok404=False):
        """Execute request to ISY REST interface."""
        if _LOGGER is not None:
            _LOGGER.info("ISY Request: %s", url)

        try:
            req = self.req_session.get(
                url, auth=(self._username, self._password), timeout=10, verify=False
            )
        except requests.ConnectionError:
            _LOGGER.error(
                "ISY Could not receive response "
                "from device because of a network "
                "issue."
            )
            return None
        except requests.exceptions.Timeout:
            _LOGGER.error("Timed out waiting for response from the ISY device.")
            return None

        if req.status_code == 200:
            _LOGGER.debug("ISY Response Received")
            return req.content.decode(encoding="utf-8", errors="ignore")
        if req.status_code == 404 and ok404:
            _LOGGER.debug("ISY Response Received")
            return ""

        _LOGGER.warning(
            "Bad ISY Request: %s %s: retry #%s", url, req.status_code, retries
        )

        if retries < MAX_RETRIES:
            # sleep for one second to allow the ISY to catch up
            time.sleep(1)
            # recurse to try again
            return self.request(url, retries + 1, ok404=False)
        # fail for good
        _LOGGER.error(
            "Bad ISY Request: %s %s: Failed after %s retries",
            url,
            req.status_code,
            retries,
        )
        return None

    def ping(self):
        """Test connection to the ISY and return True if alive."""
        req_url = self.compile_url([URL_PING])
        result = self.request(req_url, ok404=True)
        return result is not None

    def get_config(self):
        """Fetch the configuration from the ISY."""
        req_url = self.compile_url([URL_CONFIG])
        result = self.request(req_url)
        return result

    def get_programs(self, address=None):
        """Fetch the list of programs from the ISY."""
        addr = [URL_PROGRAMS]
        if address is not None:
            addr.append(str(address))
        req_url = self.compile_url(addr, {URL_SUBFOLDERS: XML_TRUE})
        result = self.request(req_url)
        return result

    def get_nodes(self):
        """Fetch the list of nodes/groups/scenes from the ISY."""
        req_url = self.compile_url([URL_NODES], {URL_MEMBERS: XML_FALSE})
        result = self.request(req_url)
        return result

    def get_status(self):
        """Fetch the status of nodes/groups/scenes from the ISY."""
        req_url = self.compile_url([URL_STATUS])
        result = self.request(req_url)
        return result

    def get_variable_defs(self):
        """Fetch the list of variables from the ISY."""
        req_list = [
            [URL_VARIABLES, URL_DEFINITIONS, VAR_INTEGER],
            [URL_VARIABLES, URL_DEFINITIONS, VAR_STATE],
        ]
        req_urls = [self.compile_url(req) for req in req_list]
        results = [self.request(req_url) for req_url in req_urls]
        return results

    def get_variables(self):
        """Fetch the variable details from the ISY to update local copy."""
        req_list = [
            [URL_VARIABLES, METHOD_GET, VAR_INTEGER],
            [URL_VARIABLES, METHOD_GET, VAR_STATE],
        ]
        req_urls = [self.compile_url(req) for req in req_list]
        results = [self.request(req_url) for req_url in req_urls]
        results = [r for r in results if r is not None]  # Strip any bad requests.
        result = "".join(results)
        result = result.replace(
            '</vars><?xml version="1.0" encoding="UTF-8"?><vars>', ""
        )
        return result

    def get_network(self):
        """Fetch the list of network resources from the ISY."""
        req_url = self.compile_url([URL_NETWORK, URL_RESOURCES])
        result = self.request(req_url)
        return result

    def get_time(self):
        """Fetch the system time info from the ISY."""
        req_url = self.compile_url([URL_CLOCK])
        result = self.request(req_url)
        return result


class TLSHttpAdapter(HTTPAdapter):
    """Transport adapter that uses TLS1."""

    def __init__(self, tls_ver):
        """Initialize the TLSHttpAdapter class."""
        if tls_ver == 1.1:
            self.tls = ssl.PROTOCOL_TLSv1_1
        elif tls_ver == 1.2:
            self.tls = ssl.PROTOCOL_TLSv1_2
        super().__init__()

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        """Initialize the Pool Manager."""
        self.poolmanager = PoolManager(
            num_pools=connections, maxsize=maxsize, block=block, ssl_version=self.tls
        )


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
