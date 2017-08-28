try:
    # python 2.7
    from urllib import quote
    from urllib import urlencode
except ImportError:
    # python 3.4
    from urllib.parse import quote
    from urllib.parse import urlencode
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.poolmanager import PoolManager
import ssl
import sys
from xml.dom import minidom

class Connection(object):

    def __init__(self, parent, address, port, username, password, use_https,
                 tls_ver):
        self.parent = parent
        self._address = address
        self._port = port
        self._username = username
        self._password = password

        # setup proper HTTPS handling for the ISY
        if use_https and can_https(self.parent.log, tls_ver):
            self._use_https = True
            self._tls_ver = tls_ver
            # Most SSL certs will not be valid. Let's not warn about them.
            requests.packages.urllib3.disable_warnings()

            # ISY uses TLS1 and not SSL
            req_session = requests.Session()
            req_session.mount(self.compileURL(None), TLSHttpAdapter(tls_ver))
        else:
            self._use_https = False
            self._tls_ver = None

        # test settings
        if not self.ping():
            # try turning off HTTPS
            self._use_https = False
            if self.ping():
                self.parent.log.warn('PyISY could not connect with the '
                                     + 'controller. Trying again with HTTP.')
            else:
                raise(ValueError('PyISY could not connect to the ISY '
                                 + 'controller with the provided attributes.'))

    # COMMON UTILITIES
    def compileURL(self, path, query=None):
        if self._use_https:
            url = 'https://'
        else:
            url = 'http://'

        url += self._address + ':{}'.format(self._port)
        if path is not None:
            url += '/rest/' + '/'.join([quote(item) for item in path])

        if query is not None:
            url += '?' + urlencode(query)

        return url

    def request(self, url, ok404=False):
        if self.parent.log is not None:
            self.parent.log.info('ISY Request: ' + url)

        try:
            r = requests.get(url, auth=(self._username, self._password),
                    timeout=10, verify=False)

        except requests.ConnectionError as err:
            self.parent.log.error('ISY Could not recieve response '
                                  + 'from device because of a network '
                                  + 'issue.')
            return None

        except requests.exceptions.Timeout:
            self.parent.log.error('Timed out waiting for response from the '
                                  + 'ISY device.')
            return None

        if r.status_code == 200:
            self.parent.log.info('ISY Response Recieved')
            # remove unicode from string in python 2.7, 3.2,
            # and 3.4 compatible way
            xml = ''.join(char for char in r.text if ord(char) < 128)
            return xml
        elif r.status_code == 404 and ok404:
            self.parent.log.info('ISY Response Recieved')
            return ''
        else:
            self.parent.log.warning('Bad ISY Request: ' + url)
            return None

    # PING
    # This is a dummy command that does not exist in the REST API
    # this function return True if the device is alive
    def ping(self):
        req_url = self.compileURL(['ping'])
        result = self.request(req_url, ok404=True)
        return result is not None

    # CONFIGURATION
    def getConfiguration(self):
        req_url = self.compileURL(['config'])
        result = self.request(req_url)
        return result

    # PROGRAMS
    def getPrograms(self, pid=None):
        addr = ['programs']
        if pid is not None:
            addr.append(str(pid))
        req_url = self.compileURL(addr, {'subfolders': 'true'})
        result = self.request(req_url)
        return result

    def programRun(self, pid):
        return self.programRunCmd(pid, 'run')

    def programRunThen(self, pid):
        return self.programRunCmd(pid, 'runThen')

    def programRunElse(self, pid):
        return self.programRunCmd(pid, 'runElse')

    def programStop(self, pid):
        return self.programRunCmd(pid, 'stop')

    def programEnable(self, pid):
        return self.programRunCmd(pid, 'enable')

    def programDisable(self, pid):
        return self.programRunCmd(pid, 'disable')

    def programEnableRunAtStartup(self, pid):
        return self.programRunCmd(pid, 'enableRunAtStartup')

    def programDisableRunAtStartup(self, pid):
        return self.programRunCmd(pid, 'disableRunAtStartup')

    def programRunCmd(self, pid, cmd):
        req_url = self.compileURL(['programs', str(pid), cmd])
        result = self.request(req_url)
        return result

    # NODES
    def getNodes(self):
        req_url = self.compileURL(['nodes'], {'members': 'false'})
        result = self.request(req_url)
        return result

    # Get the device notes xml
    def getNodeNotes(self,nid):
        req_url = self.compileURL(['nodes', nid, 'notes'])
        result = self.request(req_url,ok404=True)
        return result
    
    def updateNodes(self):
        req_url = self.compileURL(['status'])
        result = self.request(req_url)
        return result

    def updateNode(self, nid):
        req_url = self.compileURL(['nodes', nid, 'get', 'ST'])
        response = self.request(req_url)
        return response

    def nodeOff(self, nid):
        req_url = self.compileURL(['nodes', nid, 'cmd', 'DOF'])
        response = self.request(req_url)
        return response

    def nodeOn(self, nid, val=None):
        if val is None:
            req_url = self.compileURL(['nodes', nid, 'cmd', 'DON'])
        elif val > 0:
            val = str(min(255, val))
            req_url = self.compileURL(['nodes', nid, 'cmd', 'DON', val])
        elif val <= 0:
            return self.nodeOff(nid)
        response = self.request(req_url)
        return response

    def nodeFastOff(self, nid):
        req_url = self.compileURL(['nodes', nid, 'cmd', 'DFOF'])
        response = self.request(req_url)
        return response

    def nodeFastOn(self, nid):
        req_url = self.compileURL(['nodes', nid, 'cmd', 'DFON'])
        response = self.request(req_url)
        return response

    def nodeBright(self, nid):
        req_url = self.compileURL(['nodes', nid, 'cmd', 'BRT'])
        response = self.request(req_url)
        return response

    def nodeDim(self, nid):
        req_url = self.compileURL(['nodes', nid, 'cmd', 'DIM'])
        response = self.request(req_url)
        return response

    def nodeSecMd(self, nid, val=0):
        req_url = self.compileURL(['nodes', nid, 'cmd', 'SECMD', val])
        response = self.request(req_url)
        return response

    def nodeCliFS(self, nid, val=0):
        req_url = self.compileURL(['nodes', nid, 'cmd', 'CLIFS', val])
        response = self.request(req_url)
        return response

    def nodeCliMD(self, nid, val=0):
        req_url = self.compileURL(['nodes', nid, 'cmd', 'CLIMD', val])
        response = self.request(req_url)
        return response

    def nodeCliSPH(self, nid, val=0):
        req_url = self.compileURL(['nodes', nid, 'cmd', 'CLISPH', val])
        response = self.request(req_url)
        return response

    def nodeCliSPC(self, nid, val=0):
        req_url = self.compileURL(['nodes', nid, 'cmd', 'CLISPC', val])
        response = self.request(req_url)
        return response

    # VARIABLES
    def getVariables(self):
        requests = [['vars', 'definitions', '1'],
                    ['vars', 'definitions', '2'],
                    ['vars', 'get', '1'],
                    ['vars', 'get', '2']]
        req_urls = [self.compileURL(req) for req in requests]
        results = [self.request(req_url) for req_url in req_urls]
        return results

    def updateVariables(self):
        requests = [['vars', 'get', '1'],
                    ['vars', 'get', '2']]
        req_urls = [self.compileURL(req) for req in requests]
        results = [self.request(req_url) for req_url in req_urls]
        result = ''.join(results)
        result = result.replace('</vars><?xml version="1.0" encoding="UTF-8"?>'
                                + '<vars>', '')
        return result

    def updateVariable(self, vtype, vid):
        req_url = self.compileURL(['vars', 'get', str(vtype), str(vid)])
        result = self.request(req_url)
        return result

    def setVariable(self, vtype, vid, val):
        req_url = self.compileURL(['vars', 'set', str(vtype),
                                   str(vid), str(val)])
        result = self.request(req_url)
        return result

    def initVariable(self, vtype, vid, val):
        req_url = self.compileURL(['vars', 'init', str(vtype),
                                   str(vid), str(val)])
        result = self.request(req_url)
        return result

    # CLIMATE
    def getClimate(self):
        req_url = self.compileURL(['climate'])
        result = self.request(req_url)
        return result

    # NETWORK
    def getNetwork(self):
        req_url = self.compileURL(['networking', 'resources'])
        result = self.request(req_url)
        return result

    def runNetwork(self, cid):
        req_url = self.compileURL(['networking', 'resources', str(cid)])
        result = self.request(req_url, ok404=True)
        return result

    # X10
    def sendX10(self, address, code):
        req_url = self.compileURL(['X10', address, str(code)])
        result = self.request(req_url)
        return result


class TLSHttpAdapter(HTTPAdapter):
    '''
    Transport adapter that uses TLS1
    '''

    def __init__(self, tls_ver):
        if tls_ver == 1.1:
            self.tls = getattr(ssl, 'PROTOCOL_TLSv1_1')
        elif tls_ver == 1.2:
            self.tls = getattr(ssl, 'PROTOCOL_TLSv1_2')
        super(TLSHttpAdapter, self).__init__()

    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = PoolManager(num_pools=connections,
                                       maxsize=maxsize,
                                       block=block,
                                       ssl_version=self.tls)


def can_https(log, tls_ver):
    '''
    Function to verify minimum requirements to use an HTTPS connection. Returns
    boolean indicating whether HTTPS is available.

    |  log: The logger class to write results to
    '''
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
