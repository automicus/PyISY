"""Representation of ISY Nodes."""
from time import sleep
from xml.dom import minidom

from ..constants import (ATTR_ACTION, ATTR_CONTROL, ATTR_FLAG, ATTR_FOLDER,
                         ATTR_GROUP, ATTR_NAME, ATTR_NODE, ATTR_PREC,
                         ATTR_TYPE, ATTR_UOM, XML_PARSE_ERROR)
from ..helpers import (attr_from_element, attr_from_xml, parse_xml_properties,
                       value_from_xml)
from .group import Group
from .handlers import EventResult
from .node import Node


class Nodes:
    """
    This class handles the ISY nodes.

    This class can be used as a dictionary to
    navigate through the controller's structure to objects of type
    :class:`~PyISY.Nodes.Node` and :class:`~PyISY.Nodes.Group` that represent
    objects on the controller.

    |  isy: ISY class
    |  root: [optional] String representing the current navigation level's ID
    |  nids: [optional] list of node ids
    |  nnames: [optional] list of node names
    |  nparents: [optional] list of node parents
    |  nobjs: [optional] list of node objects
    |  ntypes: [optional] list of node types
    |  xml: [optional] String of xml data containing the configuration data

    :ivar all_lower_nodes: Return all nodes beneath current level
    :ivar children: A list of the object's children.
    :ivar hasChildren: Indicates if object has children
    :ivar name: The name of the current folder in navigation.
    """

    nids = []
    nnames = []
    nparents = []
    nobjs = []
    ntypes = []

    def __init__(self, isy, root=None, nids=None, nnames=None,
                 nparents=None, nobjs=None, ntypes=None, xml=None):
        """Initialize the Nodes ISY Node Manager class."""
        self.isy = isy
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
        """Return string representation of the nodes/folders/groups."""
        if self.root is None:
            return 'Folder <root>'
        ind = self.nids.index(self.root)
        if self.ntypes[ind] == ATTR_FOLDER:
            return 'Folder ({})'.format(self.root)
        if self.ntypes[ind] == ATTR_GROUP:
            return 'Group ({})'.format(self.root)
        return 'Node ({})'.format(self.root)

    def __repr__(self):
        """Create a pretty representation of the nodes/folders/groups."""
        # get and sort children
        folders = []
        groups = []
        nodes = []
        for child in self.children:
            if child[0] == ATTR_FOLDER:
                folders.append(child)
            elif child[0] == ATTR_GROUP:
                groups.append(child)
            elif child[0] == ATTR_NODE:
                nodes.append(child)

        # initialize data
        folders.sort(key=lambda x: x[1])
        groups.sort(key=lambda x: x[1])
        nodes.sort(key=lambda x: x[1])
        out = '{!s}\n{}{}{}'.format(self,
                                    self.__repr_folders__(folders),
                                    self.__repr_groups__(groups),
                                    self.__repr_nodes__(nodes)
                                    )
        return out

    def __repr_folders__(self, folders):
        """Return a representation of the folder structure."""
        out = ""
        for fold in folders:
            fold_obj = self[fold[2]]
            out += "  + {}: Folder({})\n".format(fold[1], fold[2])
            for line in repr(fold_obj).split('\n')[1:]:
                out += "  |   {}\n".format(line)
            out += "  -\n"
        return out

    @staticmethod
    def __repr_groups__(groups):
        """Return a representation of the groups structure."""
        out = ""
        for group in groups:
            out += "  {}: Group({})\n".format(group[1], group[2])
        return out

    def __repr_nodes__(self, nodes):
        """Return a representation of the nodes structure."""
        out = ""
        for node in nodes:
            node_obj = self[node[2]]
            if node_obj.hasChildren:
                out += "  + "
            else:
                out += "  "
            out += "{}: Node({})\n".format(node[1], node[2])
            if node_obj.hasChildren:
                for line in repr(node_obj).split('\n')[1:]:
                    out += "  |   {}\n".format(line)
                out += "  -\n"
        return out

    def __iter__(self):
        """Return an iterator for each node below the current nav level."""
        iter_data = self.all_lower_nodes
        return NodeIterator(self, iter_data, delta=1)

    def __reversed__(self):
        """Return the iterator in reverse order."""
        iter_data = self.all_lower_nodes
        return NodeIterator(self, iter_data, delta=-1)

    def _upmsg(self, xmldoc):
        """Update nodes from event stream message."""
        nid = value_from_xml(xmldoc, ATTR_NODE)
        nval = int(value_from_xml(xmldoc, ATTR_ACTION))
        self.get_by_id(nid).status.update(nval, force=True, silent=True)
        self.isy.log.debug('ISY Updated Node: ' + nid)

    def _controlmsg(self, xmldoc):
        """
        Pass Control events from an event stream message to nodes.

        Used for sending out to subscribers.
        """
        nid = value_from_xml(xmldoc, ATTR_NODE)
        cntrl = value_from_xml(xmldoc, ATTR_CONTROL)
        if not (nid and cntrl):
            # If there is no node associated with the control message ignore it
            return

        # Process the action and value if provided in event data.
        nval = value_from_xml(xmldoc, ATTR_ACTION, 0)
        prec = attr_from_xml(xmldoc, ATTR_ACTION, ATTR_PREC, None)
        uom = attr_from_xml(xmldoc, ATTR_ACTION, ATTR_UOM, None)

        self.get_by_id(nid).controlEvents.notify(EventResult(cntrl, nval,
                                                             prec, uom))
        self.isy.log.debug('ISY Node Control Event: %s %s %s',
                           nid, cntrl, nval)

    def parse(self, xml):
        """
        Parse the xml data.

        |  xml: String of the xml data
        """
        try:
            xmldoc = minidom.parseString(xml)
        except:
            self.isy.log.error("%s: Nodes", XML_PARSE_ERROR)
            return False

        # get nodes
        ntypes = [ATTR_FOLDER, ATTR_NODE, ATTR_GROUP]
        for ntype in ntypes:
            features = xmldoc.getElementsByTagName(ntype)

            for feature in features:
                # Get Node Information
                nid = value_from_xml(feature, 'address')
                nname = value_from_xml(feature, ATTR_NAME)
                nparent = value_from_xml(feature, 'parent')
                parent_nid = value_from_xml(feature, 'pnode')
                dev_type = value_from_xml(feature, ATTR_TYPE)
                node_def_id = value_from_xml(feature, 'nodeDefId')
                enabled = value_from_xml(feature, 'enabled')

                # Get Z-Wave Device Type Category
                devtype_cat = None
                if dev_type is not None and dev_type.startswith('4.'):
                    try:
                        devtype_cat = feature \
                            .getElementsByTagName('devtype')[0] \
                            .getElementsByTagName('cat')[0] \
                            .firstChild.toxml()
                    except IndexError:
                        devtype_cat = None

                # Process the different node types
                if ntype == ATTR_FOLDER and nid not in self.nids:
                    self.insert(nid, nname, nparent, None, ntype)
                elif ntype == ATTR_NODE:
                    if nid in self.nids:
                        self.get_by_id(nid).update(xmldoc=feature)
                        continue
                    state, aux_props = parse_xml_properties(feature)
                    self.insert(nid, nname, nparent,
                                Node(self, nid=nid, name=nname,
                                     state=state,
                                     aux_properties=aux_props,
                                     devtype_cat=devtype_cat,
                                     node_def_id=node_def_id,
                                     parent_nid=parent_nid,
                                     dev_type=dev_type,
                                     enabled=enabled),
                                ntype)
                elif ntype == ATTR_GROUP and nid not in self.nids:
                    flag = attr_from_element(feature, ATTR_FLAG)
                    # Ignore groups that contain 0x08 in the flag since
                    # that is a ISY scene that contains every device/
                    # scene so it will contain some scenes we have not
                    # seen yet so they are not defined and it includes
                    # the ISY MAC addrees in newer versions of
                    # ISY firmwares > 5.0.6+ ..
                    if int(flag) & 0x08:
                        self.isy.log.info('Skipping group flag=%s %s',
                                          flag, nid)
                        continue
                    mems = feature.getElementsByTagName('link')
                    # Build list of members
                    members = [mem.firstChild.nodeValue
                               for mem in mems]
                    # Build list of controllers
                    controllers = []
                    for mem in mems:
                        if int(attr_from_element(
                                mem, ATTR_TYPE, 0)) == 16:
                            controllers.append(mem.firstChild.nodeValue)
                    self.insert(nid, nname, nparent,
                                Group(self, nid, nname,
                                      members, controllers),
                                ntype)
            self.isy.log.info('ISY Loaded {}'.format(ntype))

    def update(self, wait_time=0):
        """
        Update the contents of the class.

        |  wait_time: [optional] Amount of seconds to wait before updating
        """
        sleep(wait_time)
        xml = self.isy.conn.request(self.isy.conn.compile_url(['status']))
        if xml is not None:
            self.parse(xml)
        else:
            self.isy.log.warning('ISY Failed to update nodes.')

    def insert(self, nid, nname, nparent, nobj, ntype):
        """
        Insert a new node into the lists.

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
        """Navigate through the node tree. Can take names or IDs."""
        try:
            self.nids.index(val)
            fun = self.get_by_id
        except ValueError:
            try:
                self.nnames.index(val)
                fun = self.get_by_name
            except ValueError:
                try:
                    val = int(val)
                    fun = self.get_by_index
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

    def __setitem__(self, item, value):
        """Set item value."""
        return None

    def get_by_name(self, val):
        """
        Get child object with the given name.

        |  val: String representing name to look for.
        """
        for i in range(len(self.nids)):
            if self.nparents[i] == self.root and self.nnames[i] == val:
                return self.get_by_index(i)
        return None

    def get_by_id(self, nid):
        """
        Get object with the given ID.

        |  nid: Integer representing node/group/folder id.
        """
        i = self.nids.index(nid)
        return self.get_by_index(i)

    def get_by_index(self, i):
        """
        Return the object at the given index in the list.

        |  i: Integer representing index of node/group/folder.
        """
        if self.ntypes[i] in [ATTR_GROUP, ATTR_NODE]:
            return self.nobjs[i]
        return Nodes(self.isy, self.nids[i], self.nids, self.nnames,
                     self.nparents, self.nobjs, self.ntypes)

    @property
    def children(self):
        """Return the children of the class."""
        out = []
        for i in range(len(self.nids)):
            if self.nparents[i] == self.root:
                out.append((self.ntypes[i], self.nnames[i], self.nids[i]))
        return out

    @property
    def hasChildren(self):
        """Return if the root has children."""
        try:
            self.nparents.index(self.root)
            return True
        except:
            return False

    @property
    def name(self):
        """Return the name of the root."""
        if self.root is None:
            return ''
        ind = self.nids.index(self.root)
        return self.nnames[ind]

    @property
    def all_lower_nodes(self):
        """Return all nodes below the current root."""
        output = []
        myname = self.name + '/'

        for dtype, name, ident in self.children:
            if dtype in [ATTR_GROUP, ATTR_NODE]:
                output.append((dtype, myname + name, ident))

            else:
                output += [(dtype2, myname + name2, ident2)
                           for (dtype2, name2, ident2)
                           in self[ident].all_lower_nodes]
        return output


class NodeIterator:
    """Iterate through a list of nodes, returning node objects."""

    def __init__(self, nodes, iter_data, delta=1):
        """Initialize a NodeIterator class."""
        self._nodes = nodes
        self._iterdata = iter_data
        self._len = len(iter_data)
        self._delta = delta

        if delta > 0:
            self._ind = 0
        else:
            self._ind = self._len - 1

    def __next__(self):
        """Get the next element in the iteration."""
        if self._ind >= self._len or self._ind < 0:
            raise StopIteration
        _, path, ident = self._iterdata[self._ind]
        self._ind += self._delta
        return (path, self._nodes[ident])

    def __len__(self):
        """Return the number of elements."""
        return self._len
