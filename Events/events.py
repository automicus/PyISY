import base64
import socket
import select
from threading import Thread
from xml.dom import minidom
from . import strings

POLL_TIME = 5


class EventStream(socket.socket):

    def __init__(self, parent):
        super(EventStream, self).__init__(socket.AF_INET, socket.SOCK_STREAM)
        self.parent = parent
        self._running = False
        self._reader = None
        self._writer = None
        self._thread = None
        self._subscribed = False
        self._connected = False

        # pull neccessary connection data
        auth_data = {'user': self.parent.conn._username,
                     'passwd': self.parent.conn._password}
        self.data = {}
        authstr = '{user}:{passwd}'.format(**auth_data)
        try:
            self.data['auth'] = base64.encodestring(authstr).strip()
        except TypeError:
            authstr = bytes(authstr, 'ascii')
            self.data['auth'] = str(base64.encodebytes(authstr))
        self.data['addr'] = self.parent.conn._address
        self.data['port'] = int(self.parent.conn._port)
        self.data['passwd'] = self.parent.conn._password

    def _NIYerror(self):
        raise NotImplementedError('Function not available while '
                                  + 'socket is closed.')

    def _mkmsg(self, msg):
        head = msg['head']
        body = msg['body']
        body = body.format(**self.data)
        length = len(body)
        head = head.format(length=length, **self.data)
        return head + body

    def _routemsg(self, msg):
        cntrl = '<control>{0}</control>'
        if cntrl.format('ST') in msg:  # NODE UPDATE
            self.parent.nodes._upmsg(msg)
        elif cntrl.format('_11') in msg:  # WEATHER UPDATE
            if self.parent.configuration['Weather Information']:
                self.parent.climate._upmsg(msg)
        elif cntrl.format('_1') in msg:  # VARIABLE OR PROGRAM UPDATE
            if '<var' in msg:  # VARIABLE
                self.parent.variables._upmsg(msg)
            elif '<id>' in msg:  # PROGRAM
                self.parent.programs._upmsg(msg)

        if 'sid=' in msg and 'sid' not in self.data:
            self._upmsg(msg)

    def _upmsg(self, xml):
        xmldoc = minidom.parseString(xml)
        features = xmldoc.getElementsByTagName('Event')
        self.data['sid'] = features[0].attributes['sid'].value
        self.parent.log.debug('ISY Updated Events Stream ID')

    @property
    def running(self):
        try:
            return self._thread.isAlive()
        except:
            return False

    @running.setter
    def running(self, val):
        self._running = bool(val)
        if self._running and not self.running:
            self.parent.log.info('ISY Starting Updates')
            self.connect()
            self.subscribe()
            self._thread = Thread(target=self.watch)
            self._thread.daemon = True
            self._thread.start()
        else:
            self.parent.log.info('ISY Stopping Updates')
            self.unsubscribe()
            self.disconnect()

    def read(self):
        if self._reader is None:
            self._NIYerror()
        else:
            try:
                return self._reader.readline()
            except socket.error:
                return ''

    def write(self, msg):
        if self._writer is None:
            self._NIYerror()
        else:
            self._writer.write(msg)
            self._writer.flush()

    def connect(self):
        if not self._connected:
            super(EventStream, self).connect((self.data['addr'],
                                              self.data['port']))
            self.setblocking(0)
            self._reader = self.makefile("r")
            self._writer = self.makefile("w")
            self._connected = True

    def disconnect(self):
        if self._connected:
            self.close()
            self._connected = False

    def subscribe(self):
        if not self._subscribed and self._connected:
            if 'sid' not in self.data:
                msg = self._mkmsg(strings.sub_msg)
                self.write(msg)
            else:
                msg = self._mkmsg(strings.resub_msg)
                self.write(msg)
            self._subscribed = True

    def unsubscribe(self):
        if self._subscribed and self._connected:
            msg = self._mkmsg(strings.unsub_msg)
            self.write(msg)
            self._subscribed = False

    def watch(self):
        if self._subscribed:
            global POLL_TIME
            while self._running and self._subscribed:
                inready, _, _ = select.select([self], [], [], POLL_TIME)

                if self in inready:
                    data = self.read()
                    if data.startswith('<?xml'):
                        data = data.strip().replace('POST reuse HTTP/1.1', '')
                        self._routemsg(data)
