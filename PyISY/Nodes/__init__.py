"""Representation of ISY Nodes."""
from time import sleep
from xml.dom import minidom

from ..constants import (
    ATTR_ACTION,
    ATTR_CONTROL,
    ATTR_FLAG,
    ATTR_FORMATTED,
    ATTR_ID,
    ATTR_INSTANCE,
    ATTR_NODE_DEF_ID,
    ATTR_PRECISION,
    ATTR_UNIT_OF_MEASURE,
    ATTR_VALUE,
    EVENT_PROPS_IGNORED,
    INSTEON_RAMP_RATES,
    PROP_RAMP_RATE,
    PROTO_GROUP,
    PROTO_INSTEON,
    PROTO_NODE_SERVER,
    PROTO_ZIGBEE,
    PROTO_ZWAVE,
    TAG_ADDRESS,
    TAG_CATEGORY,
    TAG_DEVICE_TYPE,
    TAG_ENABLED,
    TAG_FAMILY,
    TAG_FOLDER,
    TAG_GROUP,
    TAG_LINK,
    TAG_NAME,
    TAG_NODE,
    TAG_PARENT,
    TAG_PRIMARY_NODE,
    TAG_TYPE,
    URL_STATUS,
    XML_PARSE_ERROR,
    XML_TRUE,
)
from ..helpers import (
    attr_from_element,
    attr_from_xml,
    parse_xml_properties,
    value_from_xml,
)
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
    :ivar has_children: Indicates if object has children
    :ivar name: The name of the current folder in navigation.
    """

    nids = []
    nnames = []
    nparents = []
    nobjs = []
    ntypes = []

    def __init__(
        self,
        isy,
        root=None,
        nids=None,
        nnames=None,
        nparents=None,
        nobjs=None,
        ntypes=None,
        xml=None,
    ):
        """Initialize the Nodes ISY Node Manager class."""
        self.isy = isy
        self.root = root

        if (
            nids is not None
            and nnames is not None
            and nparents is not None
            and nobjs is not None
            and ntypes is not None
        ):

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
            return "Folder <root>"
        ind = self.nids.index(self.root)
        if self.ntypes[ind] == TAG_FOLDER:
            return "Folder ({})".format(self.root)
        if self.ntypes[ind] == TAG_GROUP:
            return "Group ({})".format(self.root)
        return "Node ({})".format(self.root)

    def __repr__(self):
        """Create a pretty representation of the nodes/folders/groups."""
        # get and sort children
        folders = []
        groups = []
        nodes = []
        for child in self.children:
            if child[0] == TAG_FOLDER:
                folders.append(child)
            elif child[0] == TAG_GROUP:
                groups.append(child)
            elif child[0] == TAG_NODE:
                nodes.append(child)

        # initialize data
        folders.sort(key=lambda x: x[1])
        groups.sort(key=lambda x: x[1])
        nodes.sort(key=lambda x: x[1])
        out = "{!s}\n{}{}{}".format(
            self,
            self.__repr_folders__(folders),
            self.__repr_groups__(groups),
            self.__repr_nodes__(nodes),
        )
        return out

    def __repr_folders__(self, folders):
        """Return a representation of the folder structure."""
        out = ""
        for fold in folders:
            fold_obj = self[fold[2]]
            out += "  + {}: Folder({})\n".format(fold[1], fold[2])
            for line in repr(fold_obj).split("\n")[1:]:
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
            if node_obj.has_children:
                out += "  + "
            else:
                out += "  "
            out += "{}: Node({})\n".format(node[1], node[2])
            if node_obj.has_children:
                for line in repr(node_obj).split("\n")[1:]:
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

    def update_received(self, xmldoc):
        """Update nodes from event stream message."""
        nid = value_from_xml(xmldoc, TAG_NODE)
        nval = int(value_from_xml(xmldoc, ATTR_ACTION))
        prec = attr_from_xml(xmldoc, ATTR_ACTION, ATTR_PRECISION, "0")
        uom = attr_from_xml(xmldoc, ATTR_ACTION, ATTR_UNIT_OF_MEASURE, "")
        node = self.get_by_id(nid)
        # Check if UOM/PREC have changed or were not set:
        if prec and prec != node.prec:
            node.prec = prec
        if uom and uom != node.uom:
            node.uom = uom
        self.get_by_id(nid).status.update(nval, force=True, silent=True)
        self.isy.log.debug("ISY Updated Node: " + nid)

    def control_message_received(self, xmldoc):
        """
        Pass Control events from an event stream message to nodes.

        Used for sending out to subscribers.
        """
        nid = value_from_xml(xmldoc, TAG_NODE)
        cntrl = value_from_xml(xmldoc, ATTR_CONTROL)
        if not (nid and cntrl):
            # If there is no node associated with the control message ignore it
            return

        # Process the action and value if provided in event data.
        nval = value_from_xml(xmldoc, ATTR_ACTION, 0)
        prec = attr_from_xml(xmldoc, ATTR_ACTION, ATTR_PRECISION, "0")
        uom = attr_from_xml(xmldoc, ATTR_ACTION, ATTR_UNIT_OF_MEASURE, "")
        formatted = attr_from_xml(xmldoc, ATTR_FORMATTED, nval)

        node = self.get_by_id(nid)
        if not node:
            self.isy.log.debug(
                "Received a node update for node %s but could not find a record of this "
                "node. Please try restarting the module if the problem persists, this "
                "may be due to a new node being added to the ISY since last restart.",
                nid,
            )
            return

        if cntrl == PROP_RAMP_RATE:
            nval = INSTEON_RAMP_RATES.get(nval, nval)
        if cntrl not in EVENT_PROPS_IGNORED:
            node._aux_properties[cntrl] = {
                ATTR_ID: cntrl,
                ATTR_VALUE: nval,
                ATTR_PRECISION: prec,
                ATTR_UNIT_OF_MEASURE: uom,
                ATTR_FORMATTED: formatted,
            }
        node.control_events.notify(EventResult(cntrl, nval, prec, uom, formatted))
        self.isy.log.debug("ISY Node Control Event: %s %s %s", nid, cntrl, nval)

    def parse(self, xml):
        """
        Parse the xml data.

        |  xml: String of the xml data
        """
        try:
            xmldoc = minidom.parseString(xml)
        except (AttributeError, KeyError, ValueError, TypeError, IndexError):
            self.isy.log.error("%s: Nodes", XML_PARSE_ERROR)
            return False

        # get nodes
        ntypes = [TAG_FOLDER, TAG_NODE, TAG_GROUP]
        for ntype in ntypes:
            features = xmldoc.getElementsByTagName(ntype)

            for feature in features:
                # Get Node Information
                nid = value_from_xml(feature, TAG_ADDRESS)
                nname = value_from_xml(feature, TAG_NAME)
                nparent = value_from_xml(feature, TAG_PARENT)
                parent_nid = value_from_xml(feature, TAG_PRIMARY_NODE)
                family = value_from_xml(feature, TAG_FAMILY)
                device_type = value_from_xml(feature, TAG_TYPE)
                node_def_id = attr_from_element(feature, ATTR_NODE_DEF_ID)
                enabled = value_from_xml(feature, TAG_ENABLED) == XML_TRUE

                # Assume Insteon, update as confirmed otherwise
                protocol = PROTO_INSTEON
                devtype_cat = None
                node_server = None
                if family is not None:
                    if family == "4":
                        protocol = PROTO_ZWAVE
                        try:
                            devtype_cat = (
                                feature.getElementsByTagName(TAG_DEVICE_TYPE)[0]
                                .getElementsByTagName(TAG_CATEGORY)[0]
                                .firstChild.toxml()
                            )
                        except IndexError:
                            devtype_cat = None
                    elif family in ("3", "8"):
                        protocol = PROTO_ZIGBEE
                    elif family == "10":
                        # Node Server Slot is stored with family as text:
                        node_server = attr_from_xml(feature, TAG_FAMILY, ATTR_INSTANCE)
                        if node_server:
                            protocol = f"{PROTO_NODE_SERVER}_{node_server}"

                # Process the different node types
                if ntype == TAG_FOLDER and nid not in self.nids:
                    self.insert(nid, nname, nparent, None, ntype)
                elif ntype == TAG_NODE:
                    if nid in self.nids:
                        self.get_by_id(nid).update(xmldoc=feature)
                        continue
                    state, aux_props = parse_xml_properties(feature)
                    self.insert(
                        nid,
                        nname,
                        nparent,
                        Node(
                            self,
                            nid=nid,
                            name=nname,
                            state=state,
                            aux_properties=aux_props,
                            devtype_cat=devtype_cat,
                            node_def_id=node_def_id,
                            parent_nid=parent_nid,
                            device_type=device_type,
                            enabled=enabled,
                            node_server=node_server,
                            protocol=protocol,
                            family_id=family,
                        ),
                        ntype,
                    )
                elif ntype == TAG_GROUP and nid not in self.nids:
                    flag = attr_from_element(feature, ATTR_FLAG)
                    # Ignore groups that contain 0x08 in the flag since
                    # that is a ISY scene that contains every device/
                    # scene so it will contain some scenes we have not
                    # seen yet so they are not defined and it includes
                    # the ISY MAC addrees in newer versions of
                    # ISY firmwares > 5.0.6+ ..
                    if int(flag) & 0x08:
                        self.isy.log.info("Skipping group flag=%s %s", flag, nid)
                        continue
                    mems = feature.getElementsByTagName(TAG_LINK)
                    # Build list of members
                    members = [mem.firstChild.nodeValue for mem in mems]
                    # Build list of controllers
                    controllers = []
                    for mem in mems:
                        if int(attr_from_element(mem, TAG_TYPE, 0)) == 16:
                            controllers.append(mem.firstChild.nodeValue)
                    self.insert(
                        nid,
                        nname,
                        nparent,
                        Group(self, nid, nname, members, controllers),
                        ntype,
                    )
            self.isy.log.debug("ISY Loaded {}".format(ntype))

    def update(self, wait_time=0):
        """
        Update the contents of the class.

        |  wait_time: [optional] Amount of seconds to wait before updating
        """
        sleep(wait_time)
        xml = self.isy.conn.request(self.isy.conn.compile_url([URL_STATUS]))
        if xml is not None:
            self.parse(xml)
        else:
            self.isy.log.warning("ISY Failed to update nodes.")

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
            output = None
            try:
                output = fun(val)
            except ValueError:
                pass

            if output:
                return output
        raise KeyError("Unrecognized Key: [{!s}]".format(val))

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
        try:
            i = self.nids.index(nid)
        except ValueError:
            return None
        else:
            return self.get_by_index(i)

    def get_by_index(self, i):
        """
        Return the object at the given index in the list.

        |  i: Integer representing index of node/group/folder.
        """
        if self.ntypes[i] in [TAG_GROUP, TAG_NODE]:
            return self.nobjs[i]
        return Nodes(
            self.isy,
            self.nids[i],
            self.nids,
            self.nnames,
            self.nparents,
            self.nobjs,
            self.ntypes,
        )

    @property
    def children(self):
        """Return the children of the class."""
        out = []
        for i in range(len(self.nids)):
            if self.nparents[i] == self.root:
                out.append((self.ntypes[i], self.nnames[i], self.nids[i]))
        return out

    @property
    def has_children(self):
        """Return if the root has children."""
        try:
            self.nparents.index(self.root)
            return True
        except ValueError:
            return False

    @property
    def name(self):
        """Return the name of the root."""
        if self.root is None:
            return ""
        ind = self.nids.index(self.root)
        return self.nnames[ind]

    @property
    def all_lower_nodes(self):
        """Return all nodes below the current root."""
        output = []
        myname = self.name + "/"

        for dtype, name, ident in self.children:
            if dtype in [TAG_GROUP, TAG_NODE]:
                output.append((dtype, myname + name, ident))

            else:
                output += [
                    (dtype2, myname + name2, ident2)
                    for (dtype2, name2, ident2) in self[ident].all_lower_nodes
                ]
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
