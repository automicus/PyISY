
from xml.dom import minidom
from time import sleep
from ISYtypes import MonitoredDict
from datetime import datetime

_change2update_interval = 0.5
_thread_sleeptime = 0.75

class programs(object):

    pids = []
    pnames = []
    pparents = []
    pobjs = []
    ptypes = []

    def __init__(self, parent, root=None, pids=None, pnames=None, \
        pparents=None, pobjs=None, ptypes=None, xml=None):
        
        self.parent = parent
        self.root = root

        if pids is not None and pnames is not None and pparents is not None \
            and pobjs is not None and ptypes is not None:
            
            self.pids = pids
            self.pnames = pnames
            self.pparents = pparents
            self.pobjs = pobjs
            self.ptypes = ptypes
            
        elif xml is not None:
            self.parse(xml)

    def parse(self, xml):
        try:
            xmldoc = minidom.parseString(xml)
        except:
            self.parent.log.error('ISY Could not parse programs, poorly formatted XML.')
        else:
            plastup = datetime.now()

            # get nodes
            features = xmldoc.getElementsByTagName('program')
            for feature in features:
                pid = feature.attributes['id'].value
                pname = feature.getElementsByTagName('name')[0].firstChild.toxml()
                try:
                    pparent = feature.attributes['parentId'].value
                except:
                    pparent = None
                pstatus = feature.attributes['status'].value

                if feature.attributes['folder'].value == 'true':
                    ptype = 'folder'
                    pobj = folder(self, pid, pstatus)
                
                else:
                    ptype = 'program'
                    plastrun = feature.getElementsByTagName('lastRunTime')[0].firstChild
                    if plastrun is None:
                        plastrun = datetime(1, 1, 1, 0, 0)
                    else:
                        plastrun = datetime.strptime(plastrun.toxml(), '%Y/%m/%d %I:%M:%S %p')
                    plastfin = feature.getElementsByTagName('lastFinishTime')[0].firstChild
                    if plastfin is None:
                        plastfin = datetime(1, 1, 1, 0, 0)
                    else:
                        plastfin = datetime.strptime(plastfin.toxml(), '%Y/%m/%d %I:%M:%S %p')
                    if feature.attributes['enabled'].value == 'true':
                        penabled = True
                    else:
                        penabled = False
                    if feature.attributes['runAtStartup'].value == 'true':
                        pstartrun = True
                    else:
                        pstartrun = False
                    if feature.attributes['running'].value == 'idle':
                        prunning = False
                    else:
                        prunning = True
                    pobj = program(self, pid, pstatus, plastup, plastrun, plastfin, penabled, pstartrun, prunning)

                if pid in self.pids:
                    self.getByID(pid).update(data = pobj)
                else:
                    self.insert(pid, pname, pparent, pobj, ptype)

            self.parent.log.info('ISY Loaded/Updated Programs')
                    
    def update(self, waitTime=0):
        sleep(waitTime)
        xml = self.parent.conn.getPrograms()

        if xml is not None:
            xmldoc = minidom.parseString(xml)
            self.parse(xml)
        else:
            self.parent.log.warning('ISY Failed to update programs.')
            
    def updateThread(self):
        while self.parent.auto_update:
            self.update()
            sleep(_thread_sleeptime)
    
    def insert(self, pid, pname, pparent, pobj, ptype):
        self.pids.append(pid)
        self.pnames.append(pname)
        self.pparents.append(pparent)
        self.ptypes.append(ptype)
        self.pobjs.append(pobj)
    
    def __getitem__(self, val):
        try:
            self.pids.index(val)
            fun = self.getByID
        except:
            try:
                self.pnames.index(val)
                fun = self.getByName
            except:
                val = int(val)
                fun = self.getByInd
        
        try:
            return fun(val)
        except:
            return None

    def __setitem__(self, val):
        return None

    def getByName(self, val):
        for i in xrange(len(self.pids)):
            if self.pparents[i] == self.root and self.pnames[i] == val:
                return self.getByInd(i)

    def getByID(self, nid):
        i = self.pids.index(nid)
        return self.getByInd(i, forceObj=True)

    def getByInd(self, i, forceObj=False):
        if self.ptypes[i] == 'folder' and not forceObj:
            return nodes(self.pids[i], self.parent, self.pids, self.pnames, self.pparents, self.pobjs, self.ptypes)
        else:
            return self.pobjs[i]
   

class folder(MonitoredDict):
    
    def __init__(self, parent, pid, pstatus):
        super(folder, self).__init__()
        self.noupdate = False
        self.parent = parent
        self._id = pid

        self['status'] = pstatus
            
    def update(self, waitTime=0, data=None):
        if not self.noupdate:
            if data is not None:
                self.set('status', data['status'])
            else:
                self.parent.update(waitTime)

    def run(self):
        response = self.parent.parent.conn.programRun(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not run program: ' + self._id)
        else:
            self.parent.parent.log.info('ISY ran program: ' + self._id)
            self.update(_change2update_interval)

    def runThen(self):
        response = self.parent.parent.conn.programRunThen(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not run then in program: ' + self._id)
        else:
            self.parent.parent.log.info('ISY ran then in program: ' + self._id)
            self.update(_change2update_interval)

    def runElse(self):
        response = self.parent.parent.conn.programRunElse(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not run else in program: ' + self._id)
        else:
            self.parent.parent.log.info('ISY ran else in program: ' + self._id)
            self.update(_change2update_interval)    

    def stop(self):
        response = self.parent.parent.conn.programStop(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not stop program: ' + self._id)
        else:
            self.parent.parent.log.info('ISY stopped program: ' + self._id)
            self.update(_change2update_interval)
    
class program(folder):

    def __init__(self, parent, pid, pstatus, plastup, plastrun, plastfin, penabled, pstartrun, prunning):
        super(program, self).__init__(parent, pid, pstatus)
        self['lastUpdate'] = plastup
        self['lastRun'] = plastrun
        self['lastFinished'] = plastfin
        self['enabled'] = penabled
        self.bindReporter('enabled', self.__report_enabled__)
        self['runAtStartup'] = pstartrun
        self.bindReporter('enabled', self.__report_startrun__)
        self['running'] = prunning

    def __report_enabled__(self, val):
        self.noupdate = True
        fun = self.enable if val else self.disable
        fun()
        self.noupdate = False

    def __report_startrun__(self, val):
        self.noupdate = True
        fun = self.enableRunAtStartup if val else self.disableRunAtStartup
        fun()
        self.noupdate = False

    def update(self, waitTime=0, data=None):
        if not self.noupdate:
            if data is not None:
                prunning = (data['lastRun'] >= self['lastUpdate']) or data['running']
                self.set('status', data['status'])
                self.set('lastUpdate', data['lastUpdate'])
                self.set('lastRun', data['lastRun'])
                self.set('lastFinished', data['lastFinished'])
                self.set('enabled', data['enabled'])
                self.set('runAtStartup', data['runAtStartup'])
                self.set('running', prunning)
            else:
                self.parent.update(waitTime)

    def enable(self):
        response = self.parent.parent.conn.programEnable(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not enable program: ' + self._id)
        else:
            self.parent.parent.log.info('ISY enabled program: ' + self._id)
            self.update(_change2update_interval)   

    def disable(self):
        response = self.parent.parent.conn.programDisable(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not disable program: ' + self._id)
        else:
            self.parent.parent.log.info('ISY disabled program: ' + self._id)
            self.update(_change2update_interval) 

    def enableRunAtStartup(self):
        response = self.parent.parent.conn.programEnableRunAtStartup(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not enable run at startup for program: ' + self._id)
        else:
            self.parent.parent.log.info('ISY enabled run at startup for program: ' + self._id)
            self.update(_change2update_interval) 

    def disableRunAtStartup(self):
        response = self.parent.parent.conn.programDisableRunAtStartup(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not disable run at startup for program: ' + self._id)
        else:
            self.parent.parent.log.info('ISY disabled run at startup for program: ' + self._id)
            self.update(_change2update_interval) 