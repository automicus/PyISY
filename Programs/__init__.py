from ..constants import _empty_time
from datetime import datetime
from .folder import Folder
from .program import Program
from ..Nodes import NodeIterator as ProgramIterator
from time import sleep
from xml.dom import minidom


class Programs(object):
    """
    This class handles the ISY programs.This class can be used as a dictionary
    to navigate through the controller's structure to objects of type
    :class:`~PyISY.Programs.Program` and :class:`~PyISY.Programs.Folder`
    (when requested) that represent objects on the controller.

    |  parent: The ISY device class
    |  root: Program/Folder ID representing the current level of navigation.
    |  pids: List of program and folder IDs.
    |  pnames: List of the program and folder names.
    |  pparents: List of the program and folder parent IDs.
    |  pobjs: List of program and folder objects.
    |  ptypes: List of the program and folder types.
    |  xml: XML string from the controller detailing the programs and folders.

    :ivar allLowerPrograms: A list of all programs below the current navigation
                            level. Does not return folders.
    :ivar children: A list of the children immediately below the current
                    navigation level.
    :ivar leaf: The child object representing the current item in navigation.
                This is useful for getting a folder to act as a program.
    :ivar name: The name of the program at the current level of navigation.
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
        """ Returns a string representation of the program manager. """
        if self.root is None:
            return 'Folder <root>'
        else:
            ind = self.pids.index(self.root)
            if self.ptypes[ind] == 'folder':
                return 'Folder (' + self.root + ')'
            elif self.ptypes[ind] == 'program':
                return 'Program (' + self.root + ')'

    def __repr__(self):
        """ Returns a string showing the hierarchy of the program manager. """
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

    def __iter__(self):
        """
        Returns an iterator that iterates through all the programs (not folders)
        that are beneath the current folder in navigation.
        """
        iter_data = self.allLowerPrograms
        return ProgramIterator(self, iter_data, delta=1)

    def __reversed__(self):
        """ Returns an iterator that goes in reverse order. """
        iter_data = self.allLowerPrograms
        return ProgramIterator(self, iter_data, delta=-1)

    def _upmsg(self, xmldoc):
        """Updates programs from EventStream message."""
        xml = xmldoc.toxml()
        pid = xmldoc.getElementsByTagName('id')[0].firstChild.toxml().zfill(4)
        try:
            pobj = self.getByID(pid).leaf
        except ValueError:
            pobj = None  # this is a new program that hasn't been registered

        if isinstance(pobj, Program):
            if '<s>' in xml:
                status = xmldoc.getElementsByTagName('s')[0].firstChild.toxml()
                if status == '21':
                    pobj.ranThen.update(pobj.ranThen + 1, force=True,
                                        silent=True)
                    pobj.status.update(True, force=True, silent=True)
                elif status == '31':
                    pobj.ranElse.update(pobj.ranElse + 1, force=True,
                                        silent=True)
                    pobj.status.update(False, force=True, silent=True)

            if '<r>' in xml:
                plastrun = xmldoc.getElementsByTagName('r')[0]. \
                    firstChild.toxml()
                plastrun = datetime.strptime(plastrun, '%y%m%d %H:%M:%S')
                pobj.lastRun.update(plastrun, force=True, silent=True)

            if '<f>' in xml:
                plastfin = xmldoc.getElementsByTagName('f')[0]. \
                    firstChild.toxml()
                plastfin = datetime.strptime(plastfin, '%y%m%d %H:%M:%S')
                pobj.lastFinished.update(plastfin, force=True, silent=True)

            if '<on />' in xml or '<off />' in xml:
                pobj.enabled.update('<on />' in xml, force=True, silent=True)

        self.parent.log.info('ISY Updated Program: ' + pid)

    def parse(self, xml):
        """
        Parses the XML from the controller and updates the state of the manager.

        xml: XML string from the controller.
        """
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

                # add or update object if it already exists
                if pid not in self.pids:
                    if ptype == 'folder':
                        pobj = Folder(self, pid, pname, **data)
                    else:
                        pobj = Program(self, pid, pname, **data)
                    self.insert(pid, pname, pparent, pobj, ptype)
                else:
                    pobj = self.getByID(pid).leaf
                    pobj.update(data=data)

            self.parent.log.info('ISY Loaded/Updated Programs')

    def update(self, waitTime=0, pid=None):
        """
        Update the status of the programs and folders.

        |  waitTime: How long to wait before updating.
        |  pid: The program ID to update.
        """
        sleep(waitTime)
        xml = self.parent.conn.getPrograms(pid)

        if xml is not None:
            self.parse(xml)
        else:
            self.parent.log.warning('ISY Failed to update programs.')

    def insert(self, pid, pname, pparent, pobj, ptype):
        """
        Insert a new program or folder into the manager.

        |  pid: The ID of the program or folder.
        |  pname: The name of the program or folder.
        |  pparent: The parent of the program or folder.
        |  pobj: The object representing the program or folder.
        |  ptype: The type of the item being added (program/folder).
        """
        self.pids.append(pid)
        self.pnames.append(pname)
        self.pparents.append(pparent)
        self.ptypes.append(ptype)
        self.pobjs.append(pobj)

    def __getitem__(self, val):
        """
        Navigate through the hierarchy using names or IDs.

        |  val: Name or ID to navigate to.
        """
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
        """
        Get a child program/folder with the given name.

        |  val: The name of the child program/folder to look for.
        """
        for i in range(len(self.pids)):
            if self.pparents[i] == self.root and self.pnames[i] == val:
                return self.getByInd(i)

    def getByID(self, pid):
        """
        Get a program/folder with the given ID.

        |  pid: The program/folder ID to look for.
        """
        i = self.pids.index(pid)
        return self.getByInd(i)

    def getByInd(self, i):
        """
        Get the program/folder at the given index.

        |  i: The program/folder index.
        """
        if self.ptypes[i] == 'folder':
            return Programs(self.parent, self.pids[i], self.pids, self.pnames,
                            self.pparents, self.pobjs, self.ptypes)
        else:
            return self.pobjs[i]

    @property
    def children(self):
        out = []
        for ind in range(len(self.pnames)):
            if self.pparents[ind] == self.root:
                out.append((self.ptypes[ind], self.pnames[ind],
                            self.pids[ind]))
        return out

    @property
    def leaf(self):
        if self.root is not None:
            ind = self.pids.index(self.root)
            if self.pobjs[ind] is not None:
                return self.pobjs[ind]
        return self

    @property
    def name(self):
        if self.root is not None:
            ind = self.pids.index(self.root)
            return self.pnames[ind]
        else:
            return ''

    @property
    def allLowerPrograms(self):
        output = []
        myname = self.name + '/'

        for dtype, name, ident in self.children:
            if dtype is 'program':
                output.append((dtype, myname + name, ident))

            else:
                output += [(dtype2, myname + name2, ident2)
                           for (dtype2, name2, ident2)
                           in self[ident].allLowerPrograms]
        return output
