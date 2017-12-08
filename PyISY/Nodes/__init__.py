
from .group import Group
from .node import (Node, parse_xml_properties, ATTR_ID)
from time import sleep
from xml.dom import minidom


class Nodes(object):

    """
    This class handles the ISY nodes. This class can be used as a dictionary to
    navigate through the controller's structure to objects of type
    :class:`~PyISY.Nodes.Node` and :class:`~PyISY.Nodes.Group` that represent
    objects on the controller.

    |  parent: ISY class
    |  root: [optional] String representing the current navigation level's ID
    |  nids: [optional] list of node ids
    |  nnames: [optional] list of node names
    |  nparents: [optional] list of node parents
    |  nobjs: [optional] list of node objects
    |  ntypes: [optional] list of node types
    |  xml: [optional] String of xml data containing the configuration data

    :ivar allLowerNodes: Returns all nodes beneath current level
    :ivar children: A list of the object's children.
    :ivar hasChildren: Indicates if object has children
    :ivar name: The name of the current folder in navigation.
    """

    nids = []
    nnames = []
    nparents = []
    nobjs = []
    ntypes = []

    def __init__(self, parent, root=None, nids=None, nnames=None,
                 nparents=None, nobjs=None, ntypes=None, xml=None):
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

    def __str__(self):
        """ Returns string representation of the nodes/folders/groups. """
        if self.root is None:
            return 'Folder <root>'
        else:
            ind = self.nids.index(self.root)
            if self.ntypes[ind] == 'folder':
                return 'Folder (' + self.root + ')'
            elif self.ntypes[ind] == 'group':
                return 'Group (' + self.root + ')'
            else:
                return 'Node (' + self.root + ')'

    def __repr__(self):
        """ Creates a pretty representation of the nodes/folders/groups. """
        # get and sort children
        folders = []
        groups = []
        nodes = []
        for child in self.children:
            if child[0] is 'folder':
                folders.append(child)
            elif child[0] is 'group':
                groups.append(child)
            elif child[0] is 'node':
                nodes.append(child)

        # initialize data
        folders.sort(key=lambda x: x[1])
        groups.sort(key=lambda x: x[1])
        nodes.sort(key=lambda x: x[1])
        out = str(self) + '\n' + self.__reprFolders__(folders) + \
            self.__reprGroups__(groups) + self.__reprNodes__(nodes)
        return out

    def __reprFolders__(self, folders):
        # format folders
        out = ''
        for fold in folders:
            fold_obj = self[fold[2]]
            out += '  + ' + fold[1] + ': Folder(' + fold[2] + ')\n'
            for line in repr(fold_obj).split('\n')[1:]:
                if len(line) > 0:
                    out += '  |   ' + line + '\n'
            out += '  -\n'
        return out

    def __reprGroups__(self, groups):
        # format groups
        out = ''
        for group in groups:
            out += '  ' + group[1] + ': Group(' + group[2] + ')\n'
        return out

    def __reprNodes__(self, nodes):
        # format nodes
        out = ''
        for node in nodes:
            node_obj = self[node[2]]
            if node_obj.hasChildren:
                out += '  + '
            else:
                out += '  '
            out += node[1] + ': Node(' + node[2] + ')\n'
            if node_obj.hasChildren:
                for line in repr(node_obj).split('\n')[1:]:
                    if len(line) > 0:
                        out += '  |   ' + line + '\n'
                out += '  -\n'
        return out

    def __iter__(self):
        """
        Returns an iterator for each node below the current navigation level.
        """
        iter_data = self.allLowerNodes
        return NodeIterator(self, iter_data, delta=1)

    def __reversed__(self):
        """ Returns the iterator in reverse order. """
        iter_data = self.allLowerNodes
        return NodeIterator(self, iter_data, delta=-1)

    def _upmsg(self, xmldoc):
        """Updates nodes from event stream message."""
        nid = xmldoc.getElementsByTagName('node')[0].firstChild.toxml()
        nval = int(xmldoc.getElementsByTagName('action')[0].firstChild.toxml())
        self.getByID(nid).status.update(nval, force=True, silent=True)
        self.parent.log.info('ISY Updated Node: ' + nid)

    def _controlmsg(self, xmldoc):
        """Passes Control events from an event stream message to nodes, for
        sending out to subscribers."""
        try:
            nid = xmldoc.getElementsByTagName('node')[0].firstChild.toxml()
            cntrl = xmldoc.getElementsByTagName('control')[0].firstChild.toxml()
        except IndexError:
            # If there is no node associated with the control message we ignore it
            return

        self.getByID(nid).controlEvents.notify(cntrl)
        self.parent.log.info('ISY Node Control Event: ' + nid + ' ' + cntrl)


    def parse(self, xml):
        """
        Parses the xml data.

        |  xml: String of the xml data
        """
        try:
            xmldoc = minidom.parseString(xml)
        except:
            self.parent.log.error('ISY Could not parse nodes, '
                                  + 'poorly formatted XML.')
        else:
            # get nodes
            ntypes = ['folder', 'node', 'group']
            for ntype in ntypes:
                features = xmldoc.getElementsByTagName(ntype)

                for feature in features:
                    nid = feature.getElementsByTagName('address')[0] \
                        .firstChild.toxml()
                    nname = feature.getElementsByTagName('name')[0] \
                        .firstChild.toxml()
                    try:
                        nparent = feature.getElementsByTagName('parent')[0] \
                            .firstChild.toxml()
                    except IndexError:
                        nparent = None

                    try:
                        parent_nid = feature.getElementsByTagName('pnode')[0] \
                            .firstChild.toxml()
                    except IndexError:
                        parent_nid = None

                    try:
                        type = feature.getElementsByTagName('type')[0] \
                            .firstChild.toxml()
                    except IndexError:
                        type = None

                    try:
                        nodeDefId = feature.attributes['nodeDefId'].value
                    except KeyError:
                        nodeDefId = None

                    if ntype == 'folder':
                        self.insert(nid, nname, nparent, None, ntype)
                    elif ntype == 'node':
                        (state_val, state_uom, state_prec,
                         aux_props) = parse_xml_properties(feature)

                        dimmable = '%' in state_uom

                        self.insert(nid, nname, nparent,
                                    Node(self, nid, state_val, nname,
                                         dimmable,
                                         uom=state_uom, prec=state_prec,
                                         aux_properties=aux_props,
                                         node_def_id=nodeDefId,
                                         parent_nid=parent_nid,
                                         type=type),
                                    ntype)
                    elif ntype == 'group':
                        flag = feature.attributes['flag'].value
                        # Ignore groups that contain 0x08 in the flag since that is a ISY scene that
                        # contains every device/scene so it will contain some scenes we have not
                        # seen yet so they are not defined and it includes the ISY MAC addrees in
                        # newer versions of ISY 5.0.6+ ..
                        if int(flag) & 0x08:
                            self.parent.log.info('Skipping group flag=' + flag + " " + nid )
                        else:
                            mems = feature.getElementsByTagName('link')
                            # Build list of members
                            members = [mem.firstChild.nodeValue for mem in mems]
                            # Build list of controllers
                            controllers = []
                            for mem in mems:
                                if int(mem.attributes['type'].value) == 16:
                                    controllers.append(mem.firstChild.nodeValue)
                            self.insert(nid, nname, nparent,
                                        Group(self, nid, nname, members, controllers), ntype)

            self.parent.log.info('ISY Loaded Nodes')

    def update(self, waitTime=0):
        """
        Updates the contents of the class

        |  waitTime: [optional] Amount of seconds to wait before updating
        """
        sleep(waitTime)
        xml = self.parent.conn.updateNodes()
        if xml is not None:
            try:
                xmldoc = minidom.parseString(xml)
            except:
                self.parent.log.error('ISY Could not parse nodes, '
                                      + 'poorly formatted XML.')
            else:
                for feature in xmldoc.getElementsByTagName('node'):
                    nid = feature.attributes['id'].value

                    (state_val, state_uom, state_prec,
                     aux_props) = parse_xml_properties(feature)

                    dimmable = '%' in state_uom

                    if nid in self.nids:
                        node = self.getByID(nid)
                        node.uom = state_uom
                        node.prec = state_prec
                        node.dimmable = dimmable

                        node.aux_properties = {}
                        for prop in aux_props:
                            node.aux_properties[prop.get(ATTR_ID)] = prop

                        node.status.update(state_val, silent=True)
                    else:
                        node = Node(self, id, state_val, ' ', dimmable,
                                    uom=state_uom, prec=state_prec,
                                    aux_properties=aux_props)
                        self.insert(id, ' ', None, node)

                self.parent.log.info('ISY Updated Nodes')

        else:
            self.parent.log.warning('ISY Failed to update nodes.')

    def insert(self, nid, nname, nparent, nobj, ntype):
        """
        Inserts a new node into the lists.

        |  nid: node id
        |  nname: node name
        |  nparent: node parent
        |  nobj: node object
        |  ntype: node type
        """
        self.nids.append(nid)
        self.nnames.append(nname)
        self.nparents.append(nparent)
        self.ntypes.append(ntype)
        self.nobjs.append(nobj)

    def __getitem__(self, val):
        """
        Used for navigating through the node tree. Can take names or IDs.
        """
        try:
            self.nids.index(val)
            fun = self.getByID
        except ValueError:
            try:
                self.nnames.index(val)
                fun = self.getByName
            except ValueError:
                try:
                    val = int(val)
                    fun = self.getByInd
                except ValueError:
                    fun = None

        if fun:
            try:
                output = fun(val)
            except:
                pass

            if output:
                return output
        raise KeyError('Unrecognized Key: [' + val + ']')

    def __setitem__(self, val):
        return None

    def getByName(self, val):
        """
        Gets child object with the given name.

        |  val: String representing name to look for.
        """
        for i in range(len(self.nids)):
            if self.nparents[i] == self.root and self.nnames[i] == val:
                return self.getByInd(i)

    def getByID(self, nid):
        """
        Gets object with the given ID.

        |  nid: Integer representing node/group/folder id.
        """
        i = self.nids.index(nid)
        return self.getByInd(i)

    def getByInd(self, i):
        """
        Returns the object at the given index in the list.

        |  i: Integer representing index of node/group/folder.
        """
        if self.ntypes[i] in ['group', 'node']:
            return self.nobjs[i]
        return Nodes(self.parent, self.nids[i], self.nids, self.nnames,
                     self.nparents, self.nobjs, self.ntypes)

    def parseNotes(self, notes_xml):
        spoken = None
        if notes_xml is not None and notes_xml != "":
            try:
                notesdom = minidom.parseString(notes_xml)
            except:
                self.parent.log.error('ISY Could not parse node, notes '
                                      + 'poorly formatted XML: ' + notes_xml)
            else:
                spoken_tag = notesdom.getElementsByTagName('spoken')
                if spoken_tag and len(spoken_tag) > 0 and spoken_tag[0].firstChild is not None:
                    spoken = spoken_tag[0].firstChild.toxml()
        return { "spoken": spoken }
            
    
    @property
    def children(self):
        out = []
        for i in range(len(self.nids)):
            if self.nparents[i] == self.root:
                out.append((self.ntypes[i], self.nnames[i], self.nids[i]))
        return out

    @property
    def hasChildren(self):
        try:
            self.nparents.index(self.root)
            return True
        except:
            return False

    @property
    def name(self):
        if self.root is None:
            return ''
        else:
            ind = self.nids.index(self.root)
            return self.nnames[ind]

    @property
    def allLowerNodes(self):
        output = []
        myname = self.name + '/'

        for dtype, name, ident in self.children:
            if dtype in ['group', 'node']:
                output.append((dtype, myname + name, ident))

            else:
                output += [(dtype2, myname + name2, ident2)
                           for (dtype2, name2, ident2)
                           in self[ident].allLowerNodes]
        return output

class NodeIterator(object):
    """ Iterates through a list of nodes, returning node objects. """

    def __init__(self, parent, iter_data, delta=1):
        self._parent = parent
        self._iterdata = iter_data
        self._len = len(iter_data)
        self._delta = delta

        if delta > 0:
            self._ind = 0
        else:
            self._ind = self._len - 1

    def __next__(self):
        if self._ind >= self._len or self._ind < 0:
            raise StopIteration
        _, path, ident = self._iterdata[self._ind]
        self._ind += self._delta
        return (path, self._parent[ident])

    def __len__(self):
        return self._len
