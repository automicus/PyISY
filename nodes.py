
from xml.dom import minidom
from time import sleep
from ISYtypes import MonitoredDict

_change2update_interval = 0.5
_thread_sleeptime = 0.75

class nodes(object):

    """
    nodes class

    DESCRIPTION:
        This class handles the ISY nodes.

    USAGE:
        This object may be used in a similar way as a 
        dictionary with node ids, folder names, or 
        node indices being used as keys and the ISY 
        node class will be returned.

    EXAMPLE:
        >>> a = nodes['Living Room']['Lights']
        >>> a.on()

    ATTRIBUTES:
        parent: The ISY device class
        nids: List of node command ids
        nnames: List of node command names
        nobjs: List of node command objects
        ntypes: List of node type
    """

    nids = []
    nnames = []
    nparents = []
    nobjs = []
    ntypes = []

    def __init__(self, parent, root=None, nids=None, nnames=None, \
        nparents=None, nobjs=None, ntypes=None, xml=None):
        """
        Initiates nodes class.

        parent: ISY class
        root: [optional] String representing the current ID, used for navigating folders
        nids: [optional] list of node ids
        nnames: [optional] list of node names
        nparents: [optional] list of node parents
        nobjs: [optional] list of node objects
        ntypes: [optional] list of node types
        xml: [optional] String of xml data containing the configuration data
        """
        self.parent = parent
        self.root = root

        if nids is not None and nnames is not None and nparents is not None \
            and nobjs is not None and ntypes is not None:
            
            self.nids = nids
            self.nnames = nnames
            self.nparents = nparents
            self.nobjs = nobjs
            self.ntypes = ntypes
            
        elif xml is not None:
            self.parse(xml)

    def parse(self, xml):
        """
        Parses the xml data.

        xml: String of the xml data
        """
        try:
            xmldoc = minidom.parseString(xml)
        except:
            self.parent.log.error('ISY Could not parse nodes, poorly formatted XML.')
        else:
            # get nodes
            ntypes = ['folder', 'node', 'group']
            for ntype in ntypes:
                features = xmldoc.getElementsByTagName(ntype)

                for feature in features:
                    nid = feature.getElementsByTagName('address')[0].firstChild.toxml()
                    nname = feature.getElementsByTagName('name')[0].firstChild.toxml()
                    try:
                        nparent = feature.getElementsByTagName('parent')[0].firstChild.toxml()
                    except:
                        nparent = None

                    if ntype == 'folder':
                        self.insert(nid, nname, nparent, None, ntype)
                    elif ntype == 'node':
                        nval = feature.getElementsByTagName('property')[0].attributes['value'].value
                        nval = int(nval.replace(' ', '0'))
                        self.insert(nid, nname, nparent, node(self, nid, nval), ntype)
                    elif ntype == 'group':
                        self.insert(nid, nname, nparent, group(self, nid), ntype)

            self.parent.log.info('ISY Loaded Nodes')
                    
    def update(self, waitTime=0):
        """
        Updates the contents of the class

        waitTime: [optional] Amount of seconds to wait before updating
        """
        sleep(waitTime)
        xml = self.parent.conn.updateNodes()
        if xml is not None:
            try:
                xmldoc = minidom.parseString(xml)
            except:
                self.parent.log.error('ISY Could not parse nodes, poorly formatted XML.')
            else:
                for feature in xmldoc.getElementsByTagName('node'):
                    nid = feature.attributes['id'].value
                    nval = feature.getElementsByTagName('property')[0].attributes['value'].value
                    nval = int(nval.replace(' ', '0'))
                    if nid in self.nids:
                        self.getByID(nid).set('status', nval)
                    else:
                        self.insert(nid, ' ', None, node(self, nid, nval), 'node')

                self.parent.log.info('ISY Updated Nodes')

        else:
            self.parent.log.warning('ISY Failed to update nodes.')
            
    def updateThread(self):
        """
        Continually updates the class until it is told to stop.
        Should be run in a thread.
        """
        while self.parent.auto_update:
            self.update()
            sleep(_thread_sleeptime)
    
    def insert(self, nid, nname, nparent, nobj, ntype):
        """
        Inserts a new node into the lists.

        nid: node id
        nname: node name
        nparent: node parent
        nobj: node object
        ntype: node type
        """
        self.nids.append(nid)
        self.nnames.append(nname)
        self.nparents.append(nparent)
        self.ntypes.append(ntype)
        self.nobjs.append(nobj)
    
    def __getitem__(self, val):
        try:
            self.nids.index(val)
            fun = self.getByID
        except:
            try:
                self.nnames.index(val)
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
        """
        Returns node object or nodes class at folder 
        being given a command or folder name

        val: Integer representing command id
        """
        for i in xrange(len(self.nids)):
            if self.nparents[i] == self.root and self.nnames[i] == val:
                return self.getByInd(i)

    def getByID(self, nid):
        """
        Returns node object or nodes class at folder 
        being given a command or folder id

        val: Integer representing command id
        """
        i = self.nids.index(nid)
        return self.getByInd(i)

    def getByInd(self, i):
        """
        Returns node object or nodes class at folder 
        being given a command or folder ind

        val: Integer representing command ind
        """
        if self.ntypes[i] == 'folder':
            return nodes(self.nids[i], self.parent, self.nids, self.nnames, self.nparents, self.nobjs, self.ntypes)
        else:
            return self.nobjs[i]
   

class node(MonitoredDict):

    """
    node class

    DESCRIPTION:
        This class handles ISY nodes.

    USAGE:
        This object may be used in a similar way as a 
        dictionary with parameter names being used as 
        keys and the parameter value class will be returned.

    PARAMETERS:
        status

    EXAMPLE:
        >>> a = node['status']
        255

    ATTRIBUTES:
        parent: The nodes class
        noupdate: stops automatic updating after manipulation
    """
    
    def __init__(self, parent, nid, nval):
        super(node, self).__init__()
        self.parent = parent
        self._id = nid
        self.noupdate = False

        self['status'] = nval
        self.bindReporter('status', self.__report_status__)
            
    def __report_status__(self, event):
        self.noupdate = True
        self.on(event.obj.value)
        self.noupdate = False

    def update(self, waitTime = 0):
        if not self.parent.parent.auto_update and not self.noupdate:
            sleep(waitTime)
            xml = self.parent.parent.conn.updateNode(self._id)

            if xml is not None:
                try:
                    xmldoc = minidom.parseString(xml)
                except:
                    self.parent.parent.log.error('ISY Could not parse nodes, poorly formatted XML.')
                else:
                    self.set('status', xmldoc.getElementsByTagName('property')[0].attributes['value'].value)
                    self.parent.parent.log.info('ISY updated node: ' + self._id)
            else:
                self.parent.parent.log.warning('ISY could not update node: ' + self._id)
            
    def off(self):
        response = self.parent.parent.conn.nodeOff(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not turn off node: ' + self._id)
        else:
            self.parent.parent.log.info('ISY turned off node: ' + self._id)
            self.update(_change2update_interval)

    def on(self, val=None):
        response = self.parent.parent.conn.nodeOn(self._id, val)

        if response is None:
            self.parent.parent.log.warning('ISY could not turn on node: ' + self._id)
        else:
            if val is None:
                self.parent.parent.log.info('ISY turned on node: ' + self._id)
            else:
                self.parent.parent.log.info('ISY turned on node: ' + self._id + ', To value: ' + str(val))
            self.update(_change2update_interval)

    def fastoff(self):
        response = self.parent.parent.conn.nodeFastOff(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not fast off node: ' + self._id)
        else:
            self.parent.parent.log.info('ISY turned did a fast off with node: ' + self._id)
            self.update(_change2update_interval)

    def faston(self):
        response = self.parent.parent.conn.nodeFastOn(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not fast on node: ' + self._id)
        else:
            self.parent.parent.log.info('ISY did a fast on with node: ' + self._id)
            self.update(_change2update_interval)

    def bright(self):
        response = self.parent.parent.conn.nodeBright(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not brighten node: ' + self._id)
        else:
            self.parent.parent.log.info('ISY brightened node: ' + self._id)
            self.update(_change2update_interval)

    def dim(self):
        response = self.parent.parent.conn.nodeDim(self._id)
         
        if response is None:
            self.parent.parent.log.warning('ISY could not dim node: ' + self._id)
        else:
            self.parent.parent.log.info('ISY dimmed node: ' + self._id)
            self.update(_change2update_interval)


class group(object):

    def __init__(self, parent, nid):
        self.parent = parent
        self._id = nid

    def off(self):
        response = self.parent.parent.conn.nodeOff(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not turn off scene: ' + self._id)
        else:
            self.parent.parent.log.info('ISY turned off scene: ' + self._id)
            self.parent.update(_change2update_interval)

    def on(self):
        response = self.parent.parent.conn.nodeOn(self._id, None)

        if response is None:
            self.parent.parent.log.warning('ISY could not turn on scene: ' + self._id)
        else:
            self.parent.parent.log.info('ISY turned on scene: ' + self._id)
            self.parent.update(_change2update_interval)