"""Connection to the ISY."""
try:
    # python 2.7
    from urllib import quote
    from urllib import urlencode
except ImportError:
    # python 3.4
    from urllib.parse import quote
    from urllib.parse import urlencode
import base64
import ssl
import sys
import time

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.poolmanager import PoolManager

from .constants import ATTR_INIT

MAX_RETRIES = 5


class Connection:
    """Connection object to manage connection to and interaction with ISY."""

    def __init__(self, isy, address, port, username, password, use_https,
                 tls_ver):
        """Initialize the Connection object."""
        self.isy = isy
        self._address = address
        self._port = port
        self._username = username
        self._password = password

        self.req_session = requests.Session()

        # setup proper HTTPS handling for the ISY
        if use_https and can_https(self.isy.log, tls_ver):
            self.use_https = True
            self._tls_ver = tls_ver
            # Most SSL certs will not be valid. Let's not warn about them.
            requests.packages.urllib3.disable_warnings()

            # ISY uses TLS1 and not SSL
            self.req_session.mount(self.compile_url(None),
                                   TLSHttpAdapter(tls_ver))
        else:
            self.use_https = False
            self._tls_ver = None

        # test settings
        if not self.ping():
            # try turning off HTTPS
            self.use_https = False
            if self.ping():
                self.isy.log.warn('PyISY could not connect with the '
                                  'controller. Trying again with HTTP.')
            else:
                raise(ValueError('PyISY could not connect to the ISY '
                                 'controller with the provided attributes.'))

    @property
    def connection_info(self):
        """Return the connection info required to connect to the ISY."""
        connection_info = {}
        authstr = '{!s}:{!s}'.format(self._username, self._password)
        try:
            connection_info['auth'] = base64.encodestring(authstr).strip()
        except TypeError:
            authstr = bytes(authstr, 'ascii')
            connection_info['auth'] = base64.encodebytes(authstr) \
                .strip().decode('ascii')
        connection_info['addr'] = self._address
        connection_info['port'] = int(self._port)
        connection_info['passwd'] = self._password
        if self._tls_ver:
            connection_info['tls'] = self._tls_ver

        return connection_info

    # COMMON UTILITIES
    def compile_url(self, path, query=None):
        """Compile the URL to fetch from the ISY."""
        if self.use_https:
            url = 'https://'
        else:
            url = 'http://'

        url += self._address + ':{}'.format(self._port)
        if path is not None:
            url += '/rest/' + '/'.join([quote(item) for item in path])

        if query is not None:
            url += '?' + urlencode(query)

        return url

    def request(self, url, retries=0, ok404=False):
        """Execute request to ISY REST interface."""
        if self.isy.log is not None:
            self.isy.log.info('ISY Request: ' + url)

        try:
            req = self.req_session.get(url,
                                       auth=(self._username, self._password),
                                       timeout=10,
                                       verify=False)
        except requests.ConnectionError:
            self.isy.log.error('ISY Could not recieve response '
                               'from device because of a network '
                               'issue.')
            return None
        except requests.exceptions.Timeout:
            self.isy.log.error('Timed out waiting for response from the '
                               'ISY device.')
            return None

        if req.status_code == 200:
            self.isy.log.debug('ISY Response Recieved')
            # remove unicode from string in python 2.7, 3.2,
            # and 3.4 compatible way
            xml = ''.join(char for char in req.text if ord(char) < 128)
            return xml
        if req.status_code == 404 and ok404:
            self.isy.log.debug('ISY Response Recieved')
            return ''

        self.isy.log.warning('Bad ISY Request: %s %s: retry #%s',
                             url, req.status_code, retries)

        # sleep for one second to allow the ISY to catch up
        time.sleep(1)

        if retries < MAX_RETRIES:
            # recurse to try again
            return self.request(url, retries+1, ok404=False)
        # fail for good
        self.isy.log.error('Bad ISY Request: %s %s: '
                           'Failed after %s retries',
                           url, req.status_code, retries)
        return None

    def ping(self):
        """Test connection to the ISY and return True if alive."""
        req_url = self.compile_url(['ping'])
        result = self.request(req_url, ok404=True)
        return result is not None

    # CONFIGURATION
    def getConfiguration(self):
        req_url = self.compile_url(['config'])
        result = self.request(req_url)
        return result

    # PROGRAMS
    def getPrograms(self, pid=None):
        addr = ['programs']
        if pid is not None:
            addr.append(str(pid))
        req_url = self.compile_url(addr, {'subfolders': 'true'})
        result = self.request(req_url)
        return result

    def program_run_cmd(self, pid, cmd):
        req_url = self.compile_url(['programs', str(pid), cmd])
        result = self.request(req_url)
        return result

    # NODES
    def getNodes(self):
        req_url = self.compile_url(['nodes'], {'members': 'false'})
        result = self.request(req_url)
        return result

    # Get the device notes xml
    def get_node_notes(self, nid):
        req_url = self.compile_url(['nodes', nid, 'notes'])
        result = self.request(req_url, ok404=True)
        return result

    def updateNodes(self):
        req_url = self.compile_url(['status'])
        result = self.request(req_url)
        return result

    def updateNode(self, nid):
        req_url = self.compile_url(['nodes', nid, 'get', 'ST'])
        response = self.request(req_url)
        return response

    def node_send_cmd(self, nid, cmd, val=None):
        """Send command to a specific node."""
        req = ['nodes', nid, 'cmd', cmd]
        if val:
            req.append(val)
        req_url = self.compile_url(req)
        response = self.request(req_url)
        return response

    # VARIABLES
    def getVariables(self):
        requests = [['vars', 'definitions', '1'],
                    ['vars', 'definitions', '2'],
                    ['vars', 'get', '1'],
                    ['vars', 'get', '2']]
        req_urls = [self.compile_url(req) for req in requests]
        results = [self.request(req_url) for req_url in req_urls]
        return results

    def updateVariables(self):
        requests = [['vars', 'get', '1'],
                    ['vars', 'get', '2']]
        req_urls = [self.compile_url(req) for req in requests]
        results = [self.request(req_url) for req_url in req_urls]
        result = ''.join(results)
        result = result.replace('</vars><?xml version="1.0" encoding="UTF-8"?>'
                              '<vars>', '')
        return result

    def updateVariable(self, vtype, vid):
        req_url = self.compile_url(['vars', 'get', str(vtype), str(vid)])
        result = self.request(req_url)
        return result

    def setVariable(self, vtype, vid, val):
        req_url = self.compile_url(['vars', 'set', str(vtype),
                                   str(vid), str(val)])
        result = self.request(req_url)
        return result

    def initVariable(self, vtype, vid, val):
        req_url = self.compile_url(['vars', ATTR_INIT, str(vtype),
                                   str(vid), str(val)])
        result = self.request(req_url)
        return result

    # CLIMATE
    def getClimate(self):
        req_url = self.compile_url(['climate'])
        result = self.request(req_url)
        return result

    # NETWORK
    def getNetwork(self):
        req_url = self.compile_url(['networking', 'resources'])
        result = self.request(req_url)
        return result

    def runNetwork(self, cid):
        req_url = self.compile_url(['networking', 'resources', str(cid)])
        result = self.request(req_url, ok404=True)
        return result

    # X10
    def sendX10(self, address, code):
        req_url = self.compile_url(['X10', address, str(code)])
        result = self.request(req_url)
        return result


class TLSHttpAdapter(HTTPAdapter):
    """Transport adapter that uses TLS1."""

    def __init__(self, tls_ver):
        """Initialize the TLSHttpAdapter class."""
        if tls_ver == 1.1:
            self.tls = getattr(ssl, 'PROTOCOL_TLSv1_1')
        elif tls_ver == 1.2:
            self.tls = getattr(ssl, 'PROTOCOL_TLSv1_2')
        super(TLSHttpAdapter, self).__init__()

    def init_poolmanager(self, connections, maxsize,
                         block=False, **pool_kwargs):
        """Initialize the Pool Manager."""
        self.poolmanager = PoolManager(num_pools=connections,
                                       maxsize=maxsize,
                                       block=block,
                                       ssl_version=self.tls)


def can_https(log, tls_ver):
    """
    Verify minimum requirements to use an HTTPS connection.

    Returns boolean indicating whether HTTPS is available.

    |  log: The logger class to write results to
    """
    output = True

    # check python version
    py_version = sys.version_info
    if py_version.major == 3:
        req_version = (3, 4)
    else:
        req_version = (2, 7, 9)
    if py_version < req_version:
        log.error('PyISY cannot use HTTPS: Invalid Python version. See docs.')
        output = False

    # check that Python was compiled against correct OpenSSL lib
    if 'PROTOCOL_TLSv1_1' not in dir(ssl):
        log.error('PyISY cannot use HTTPS: Compiled against old OpenSSL '
                  + 'library. See docs.')
        output = False

    # check the requested TLS version
    if tls_ver not in [1.1, 1.2]:
        log.error('PyISY cannot use HTTPS: Only TLS 1.1 and 1.2 are supported '
                  + 'by the ISY controller.')
        output = False

    return output
