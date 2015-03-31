from ..constants import _empty_time
from datetime import datetime
from .folder import Folder
from .program import Program
from time import sleep
from xml.dom import minidom


class Programs(object):

    """
    Programs class

    DESCRIPTION:
        This class handles the ISY programs.

    ATTRIBUTES:
        parent: The ISY device class
        nids: List of node command ids
        nnames: List of node command names
        nobjs: List of node command objects
        ntypes: List of node type
        children: Names and IDs of the next level of programs
    """

    pids = []
    pnames = []
    pparents = []
    pobjs = []
    ptypes = []

    def __init__(self, parent, root=None, pids=None, pnames=None,
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

    def __str__(self):
        if self.root is None:
            return 'Folder <root>'
        else:
            ind = self.pids.index(self.root)
            if self.ptypes[ind] == 'folder':
                return 'Folder (' + self.root + ')'
            elif self.ptypes[ind] == 'program':
                return 'Program (' + self.root + ')'

    def __repr__(self):
        # get and sort children
        folders = []
        programs = []
        for child in self.children:
            if child[0] is 'folder':
                folders.append(child)
            elif child[0] is 'program':
                programs.append(child)

        # initialize data
        folders.sort(key=lambda x: x[1])
        programs.sort(key=lambda x: x[1])
        out = str(self) + '\n'

        # format folders
        for fold in folders:
            fold_obj = self[fold[2]]
            out += '  + ' + fold[1] + ': Folder(' + fold[2] + ')\n'
            for line in repr(fold_obj).split('\n')[1:]:
                if len(line) > 0:
                    out += '  |   ' + line + '\n'
            out += '  -\n'

        # format programs
        for prog in programs:
            out += '  ' + prog[1] + ': ' + self[prog[2]].__str__() + '\n'

        return out

    # fwd getattr and setattr to the child class when necessary
    def __getattr__(self, name):
        if self.root is not None:
            ind = self.pids.index(self.root)
            return getattr(self.pobjs[ind], name)

    def __setattr__(self, name, val):
        try:
            super(Programs, self).__setattr__(name, val)
        except Exception as e:
            if self.root is not None:
                ind = self.pids.index(self.root)
                setattr(self.pobjs[ind], name, val)
            else:
                raise e

    def __dir__(self):
        out = super(Programs, self).__dir__()
        if self.root is not None:
            ind = self.pid.index(self.root)
            out += dir(self.pobjs[ind])
        return out

    def _upmsg(self, xml):
        """Updates programs from EventStream message."""
        xmldoc = minidom.parseString(xml)
        pid = xmldoc.getElementsByTagName('id')[0].firstChild.toxml().zfill(4)
        pobj = self.getByID(pid)

        if '<s>' in xml:
            status = xmldoc.getElementsByTagName('s')[0].firstChild.toxml()
            if status == '21':
                pobj.ranThen.update(pobj.ranThen + 1, force=True, silent=True)
            elif status == '31':
                pobj.ranElse.update(self.ranElse + 1, force=True, silent=True)

        if '<r>' in xml:
            plastrun = xmldoc.getElementsByTagName('r')[0].firstChild.toxml()
            plastrun = datetime.strptime(plastrun, '%y%m%d %H:%M:%S')
            pobj.lastRun.update(plastrun, force=True, silent=True)

        if '<f>' in xml:
            plastfin = xmldoc.getElementsByTagName('f')[0].firstChild.toxml()
            plastfin = datetime.strptime(plastfin, '%y%m%d %H:%M:%S')
            pobj.lastFinished.update(plastfin, force=True, silent=True)

        if '<on />' in xml or '<off />' in xml:
            pobj.enabled.update('<on />' in xml, force=True, silent=True)

        self.parent.log.debug('ISY Updated Program: ' + pid)

    def parse(self, xml):
        try:
            xmldoc = minidom.parseString(xml)
        except:
            self.parent.log.error('ISY Could not parse programs, '
                                  + 'poorly formatted XML.')
        else:
            plastup = datetime.now()

            # get nodes
            features = xmldoc.getElementsByTagName('program')
            for feature in features:
                # id, name, and status
                pid = feature.attributes['id'].value
                pname = feature.getElementsByTagName('name')[0] \
                    .firstChild.toxml()
                try:
                    pparent = feature.attributes['parentId'].value
                except:
                    pparent = None
                pstatus = feature.attributes['status'].value == 'true'

                if feature.attributes['folder'].value == 'true':
                    # folder specific parsing
                    ptype = 'folder'
                    data = {'pstatus': pstatus}

                else:
                    # program specific parsing
                    ptype = 'program'

                    # last run time
                    try:
                        tag = 'lastRunTime'
                        plastrun = feature.getElementsByTagName(tag)
                        plastrun = plastrun[0].firstChild
                        if plastrun is None:
                            plastrun = _empty_time
                        else:
                            plastrun = datetime.strptime(
                                plastrun.toxml(), '%Y/%m/%d %I:%M:%S %p')
                    except:
                        plastrun = _empty_time

                    # last finish time
                    try:
                        tag = 'lastFinishTime'
                        plastfin = feature.getElementsByTagName(tag)
                        plastfin = plastfin[0].firstChild
                        if plastfin is None:
                            plastfin = _empty_time
                        else:
                            plastfin = datetime.strptime(
                                plastfin.toxml(), '%Y/%m/%d %I:%M:%S %p')
                    except:
                        plastfin = _empty_time

                    # enabled, run at startup, running
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

                    # create data dictionary
                    data = {'pstatus': pstatus, 'plastrun': plastrun,
                            'plastfin': plastfin, 'penabled': penabled,
                            'pstartrun': pstartrun, 'prunning': prunning,
                            'plastup': plastup}

                # add or skip object if it already exists
                if pid not in self.pids:
                    if ptype == 'folder':
                        pobj = Folder(self, pid, **data)
                    else:
                        pobj = Program(self, pid, **data)
                    self.insert(pid, pname, pparent, pobj, ptype)

            self.parent.log.info('ISY Loaded/Updated Programs')

    def update(self, waitTime=0, pid=None):
        sleep(waitTime)
        xml = self.parent.conn.getPrograms(pid)

        if xml is not None:
            self.parse(xml)
        else:
            self.parent.log.warning('ISY Failed to update programs.')

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
                try:
                    val = int(val)
                    fun = self.getByInd
                except:
                    raise KeyError('Unrecognized Key: ' + str(val))

        try:
            return fun(val)
        except:
            return None

    def __setitem__(self, val):
        return None

    def getByName(self, val):
        for i in range(len(self.pids)):
            if self.pparents[i] == self.root and self.pnames[i] == val:
                return self.getByInd(i)

    def getByID(self, nid):
        i = self.pids.index(nid)
        return self.getByInd(i)

    def getByInd(self, i):
        if self.ptypes[i] == 'folder':
            return Programs(self.parent, self.pids[i], self.pids, self.pnames,
                            self.pparents, self.pobjs, self.ptypes)
        else:
            return self.pobjs[i]

    @property
    def children(self):
        """Returns a list of the current objects children names and IDs."""
        out = []
        for ind in range(len(self.pnames)):
            if self.pparents[ind] == self.root:
                out.append((self.ptypes[ind], self.pnames[ind],
                            self.pids[ind]))
        return out
