import base64
import datetime
import socket
import select
from threading import Thread
import xml
from xml.dom import minidom
from . import strings

POLL_TIME = 5

class EventStream(socket.socket):

    def __init__(self, parent, lost_fun=None):
        super(EventStream, self).__init__(socket.AF_INET, socket.SOCK_STREAM)
        self.parent = parent
        self._running = False
        self._reader = None
        self._writer = None
        self._thread = None
        self._subscribed = False
        self._connected = False
        self._lasthb = None
        self._hbwait = 0
        self._lostfun = lost_fun

        # pull neccessary connection data
        auth_data = {'user': self.parent.conn._username,
                     'passwd': self.parent.conn._password}
        self.data = {}
        authstr = '{user}:{passwd}'.format(**auth_data)
        try:
            self.data['auth'] = base64.encodestring(authstr).strip()
        except TypeError:
            authstr = bytes(authstr, 'ascii')
            self.data['auth'] = base64.encodebytes(authstr) \
                .strip().decode('ascii')
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
        # check xml formatting
        try:
            xmldoc = minidom.parseString(msg)
        except xml.parsers.expat.ExpatError:
            self.parent.log.warning('ISY Received Malformed XML:\n' + msg)
            return
        self.parent.log.debug('ISY data Received:\n' + msg)

        # direct the event message
        try:
            cntrl = xmldoc.getElementsByTagName('control')[0].firstChild.toxml()
        except IndexError:
            # No control tag
            pass
        else:
            if cntrl == '_0':  # ISY HEARTBEAT
                self._lasthb = datetime.datetime.now()
                self._hbwait = int(xmldoc.getElementsByTagName('action')[0].
                                   firstChild.toxml())
                self.parent.log.debug('ISY HEARTBEAT: ' + self._lasthb.isoformat())
            if cntrl == 'ST':  # NODE UPDATE
                self.parent.nodes._upmsg(xmldoc)
            if  cntrl[0] != '_': # NODE CONTROL EVENT
                self.parent.nodes._controlmsg(xmldoc)
            elif cntrl == '_11':  # WEATHER UPDATE
                if self.parent.configuration['Weather Information']:
                    self.parent.climate._upmsg(xmldoc)
            elif cntrl == '_1':  # VARIABLE OR PROGRAM UPDATE
                if '<var' in msg:  # VARIABLE
                    self.parent.variables._upmsg(xmldoc)
                elif '<id>' in msg:  # PROGRAM
                    self.parent.programs._upmsg(xmldoc)

        # A wild stream id appears!
        if 'sid=' in msg and 'sid' not in self.data:
            self._upmsg(xmldoc)

    def _upmsg(self, xmldoc):
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
        if val and not self.running:
            self.parent.log.info('ISY Starting Updates')
            if self.connect():
                self.subscribe()
                self._running = True
                self._thread = Thread(target=self.watch)
                self._thread.daemon = True
                self._thread.start()
        else:
            self.parent.log.info('ISY Stopping Updates')
            self._running = False
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
            try:
                super(EventStream, self).connect((self.data['addr'],
                                                self.data['port']))
            except OSError:
                self.parent.log.error('PyISY could not connect to ISY ' +
                                      'event stream.')
                if self._lostfun is not None:
                    self._lostfun()
                return False
            self.setblocking(0)
            self._reader = self.makefile("r")
            self._writer = self.makefile("w")
            self._connected = True
            return True
        else:
            return True

    def disconnect(self):
        if self._connected:
            self.close()
            self._connected = False
            self._subscribed = False
            self._running = False

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
            self.disconnect()

    @property
    def heartbeat_time(self):
        if self._lasthb is not None:
            return (datetime.datetime.now() - self._lasthb).seconds
        else:
            return 0.

    def watch(self):
        if self._subscribed:
            while self._running and self._subscribed:
                # verify connection is still alive
                if self.heartbeat_time > self._hbwait:
                    self.disconnect()
                    self.parent.log.warning('PyISY lost connection to '
                                            + 'the ISY event stream.')
                    if self._lostfun is not None:
                        self._lostfun()

                # poll socket for new data
                inready, _, _ = select.select([self], [], [], POLL_TIME)
                # New code to correctly parse all messages in the buffer
                if self in inready:                
                  self.parent.log.debug('PyISY: about to process incoming messages')
                  loop     = True
                  currPos  = 0
                  tmp_buff = ''
                  retries  = 5
                  while loop:
                    try:
                      newData = self.recv(4096).decode("utf-8")      # See if we can retrieve the data 
                      self.parent.log.debug('PyISY: appended ' + str(len(newData)) + ' chars to buffer')
                    except socket.error:
                      self.parent.log.debug('PyISY: no additional data') 
                    else:                    
                      if len(newData) > 0:                           # if new data was found,
                        subsConf = newData.find('</s:Envelope>')     # check if it has a subs confirmation
                        if subsConf > -1:                            # and remove it, as we don't use it
                          newData = newData[subsConf+13:]
                          self.parent.log.debug('PyISY: skipped subscription confirmation')
                        tmp_buff = tmp_buff[currPos:] + newData      # purge old data in buffer, add new one
                        currPos = 0                                  # and move marker to beginning
                    eventStart = tmp_buff.find('<?xml', currPos)     # look for a new massage start
                    eventEnd   = tmp_buff.find('</Event>', currPos)  # and its end
                    #self.parent.log.debug('PyISY: size: '+str(len(tmp_buff))+' pos: '+str(currPos)+' start: '+str(eventStart)+' end: '+str(eventEnd))
                    #self.parent.log.debug('PyISY: buffer:\n'+tmp_buff[currPos:])
                    if eventStart > -1:                              
                       if eventEnd > eventStart:                     # if we got a complete message
                          data = tmp_buff[eventStart : eventEnd + 8] # then get it and 
                          self.parent.log.debug('PyISY: routing data')
                          self._routemsg(data)                       # send it for processing, 
                          currPos = eventEnd + 8                     # then move our marker to the
                          retries = 5                                # message end, allowing for 5 retries
                       elif eventEnd == -1:                          #  
                          retries -= 1                               # if we're missing the end, then try again
                          if retries == 0:                           # but if we're out of chances, just abort 
                            self.parent.log.warning('PyISY: Malformed event data: '+tmp_buff[currPos:])
                            break
                    else:
                      if eventEnd > -1:                            # if just found a message end but so start
                            self.parent.log.warning('PyISY: Malformed event data: '+tmp_buff[currPos:])
                            currPos = eventEnd + 8                    # inform and skip it
                      if currPos < len(tmp_buff):                      # Have we done the whole buffer?
                        if eventStart == -1 and eventEnd == -1:       #   if not, allow for rest of buffer to arrive 
                           retries -= 1                               #   and retry 
                           if retries == 0:                           #   until we run out of chances
                             self.parent.log.debug('PyISY: no more events in buffer')
                             break
                      else:
                        break
                    self.parent.log.debug('PyISY: No more messages in batch\n')
