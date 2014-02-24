
from xml.dom import minidom
from time import sleep
from ISYtypes import MonitoredDict
from datetime import datetime

_change2update_interval = 0.5
_thread_sleeptime = 0.75

class variables(object):

    vids = []
    vnames = []
    vobjs = []
    vtypes = []

    def __init__(self, parent, root=None, vids=None, vnames=None, \
        vobjs=None, vtypes=None, xml=None):
        
        self.parent = parent
        self.root = root

        if vids is not None and vnames is not None \
            and vobjs is not None and vtypes is not None:
            
            self.vids = vids
            self.vnames = vnames
            self.vobjs = vobjs
            self.vtypes = vtypes
            
        elif xml is not None:
            self.parse(xml)

    def parse(self, xmls):
        try:
            xmldocs = [minidom.parseString(xml) for xml in xmls]
        except:
            self.parent.log.error('ISY Could not parse variables, poorly formatted XML.')
        else:
            vlastup = datetime.now()

            # parse definitions
            for ind in xrange(2):
                features = xmldocs[ind].getElementsByTagName('e')
                for feature in features:
                    self.vids.append(int(feature.attributes['id'].value))
                    self.vnames.append(feature.attributes['name'].value)
                    self.vtypes.append(ind+1)

            # parse values
            count = 0
            for ind in xrange(2,4):
                features = xmldocs[ind].getElementsByTagName('var')
                for feature in features:
                    init = feature.getElementsByTagName('init')[0].firstChild.toxml()
                    val = feature.getElementsByTagName('val')[0].firstChild.toxml()
                    ts_raw = feature.getElementsByTagName('ts')[0].firstChild.toxml()
                    ts = datetime.strptime(ts_raw, '%Y%m%d %H:%M:%S')
                    self.vobjs.append(variable(self, self.vids[count], ind-1, init, val, ts))
                    count += 1

            self.parent.log.info('ISY Loaded Variables')
                    
    def update(self, waitTime=0):
        sleep(waitTime)
        xml = self.parent.conn.updateVariables()

        if xml is not None:
            #try:
                xmldoc = minidom.parseString(xml)

                features = xmldoc.getElementsByTagName('var')
                for feature in features:
                    vid = int(feature.attributes['id'].value)
                    vtype = int(feature.attributes['type'].value)
                    init = feature.getElementsByTagName('init')[0].firstChild.toxml()
                    val = feature.getElementsByTagName('val')[0].firstChild.toxml()
                    ts_raw = feature.getElementsByTagName('ts')[0].firstChild.toxml()
                    ts = datetime.strptime(ts_raw, '%Y%m%d %H:%M:%S')

                    vobj = self[vtype][vid]
                    if vobj is None:
                        vobj = variable(self, vid, vtype, init, val, ts)
                        self.vtypes.append(vtype)
                        self.vids.append(vid)
                        self.vnames.append('')
                        self.vobjs.append(vobj)
                    else:
                        vobj.set('init', init)
                        vobj.set('val', val)
                        vobj.set('lastEdit', ts)

            #except:
            #    self.parent.log.warning('ISY Failed to update variables, recieved bad XML.')

        else:
            self.parent.log.warning('ISY Failed to update variables.')
            
    def updateThread(self):
        while self.parent.auto_update:
            self.update(_thread_sleeptime)
    
    def __getitem__(self, val):
        if self.root is None:
            if val in [1, 2]:
                return variables(self.parent, val, self.vids, self.vnames, self.vobjs, self.vtypes)
            else:
                self.parent.log.error('ISY Unknown variable type: ' + str(val))

        else:
            if type(val) is int:
                search_arr = self.vids
            else:
                search_arr = self.vnames

            notFound = True
            ind = -1
            while notFound:
                try:
                    ind = search_arr.index(val, ind+1)
                    if self.vtypes[ind] == self.root:
                        notFound = False
                except ValueError:
                    break
            if notFound:
                return None
            else:
                return self.vobjs[ind]

    def __setitem__(self, val):
        return None   

class variable(MonitoredDict):
    
    def __init__(self, parent, vid, vtype, init, val, ts):
        super(variable, self).__init__()
        self.noupdate = False
        self.parent = parent
        self._id = vid
        self._type = vtype

        self['init'] = init
        self.bindReporter('init', self.__report_init__)
        self['val'] = val
        self.bindReporter('val', self.__report_val__)
        self['lastEdit'] = ts

    def __report_init__(self, val):
        self.noupdate = True
        self.setInit(val)
        self.noupdate = False

    def __report_val__(self, val):
        self.noupdate = True
        self.setValue(val)
        self.noupdate = False
            
    def update(self, waitTime=0):
        if not self.noupdate:
            self.parent.update(waitTime)

    def setInit(self, val):
        response = self.parent.parent.conn.initVariable(self._type, self._id, val)

        if response is None:
            self.parent.parent.log.warning('ISY could not set variable init value: ' + str(self._type) + ', ' + str(self._id))
        else:
            self.parent.parent.log.info('ISY set variable init value: ' + str(self._type) + ', ' + str(self._id))
            self.update(_change2update_interval)

    def setValue(self, val):
        response = self.parent.parent.conn.setVariable(self._type, self._id, val)

        if response is None:
            self.parent.parent.log.warning('ISY could not set variable: ' + str(self._type) + ', ' + str(self._id))
        else:
            self.parent.parent.log.info('ISY set variable: ' + str(self._type) + ', ' + str(self._id))
            self.update(_change2update_interval)