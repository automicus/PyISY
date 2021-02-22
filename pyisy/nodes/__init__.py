"""Representation of ISY Nodes."""
from asyncio import sleep
from xml.dom import minidom

from ..constants import (
    _LOGGER,
    ATTR_ACTION,
    ATTR_CONTROL,
    ATTR_FLAG,
    ATTR_ID,
    ATTR_INSTANCE,
    ATTR_NODE_DEF_ID,
    ATTR_PRECISION,
    ATTR_UNIT_OF_MEASURE,
    DEFAULT_PRECISION,
    DEFAULT_UNIT_OF_MEASURE,
    EVENT_PROPS_IGNORED,
    FAMILY_BRULTECH,
    FAMILY_NODESERVER,
    FAMILY_RCS,
    FAMILY_ZWAVE,
    INSTEON_RAMP_RATES,
    ISY_VALUE_UNKNOWN,
    NC_NODE_ERROR,
    NODE_CHANGED_ACTIONS,
    PROP_COMMS_ERROR,
    PROP_RAMP_RATE,
    PROP_STATUS,
    PROTO_INSTEON,
    PROTO_NODE_SERVER,
    PROTO_ZIGBEE,
    PROTO_ZWAVE,
    TAG_ADDRESS,
    TAG_DEVICE_TYPE,
    TAG_ENABLED,
    TAG_FAMILY,
    TAG_FOLDER,
    TAG_FORMATTED,
    TAG_GROUP,
    TAG_LINK,
    TAG_NAME,
    TAG_NODE,
    TAG_PARENT,
    TAG_PRIMARY_NODE,
    TAG_TYPE,
    UOM_SECONDS,
    XML_TRUE,
)
from ..exceptions import XML_ERRORS, XML_PARSE_ERROR, ISYResponseParseError
from ..helpers import (
    NodeProperty,
    ZWaveProperties,
    attr_from_element,
    attr_from_xml,
    parse_xml_properties,
    value_from_xml,
)
from .group import Group
from .node import Node


class Nodes:
    """
    This class handles the ISY nodes.

    This class can be used as a dictionary to
    navigate through the controller's structure to objects of type
    :class:`pyisy.nodes.Node` and :class:`pyisy.nodes.Group` that represent
    objects on the controller.

    |  isy: ISY class
    |  root: [optional] String representing the current navigation level's ID
    |  addresses: [optional] list of node ids
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

    def __init__(
        self,
        isy,
        root=None,
        addresses=None,
        nnames=None,
        nparents=None,
        nobjs=None,
        ntypes=None,
        xml=None,
    ):
        """Initialize the Nodes ISY Node Manager class."""
        self.isy = isy
        self.root = root

        self.addresses = []
        self.nnames = []
        self.nparents = []
        self.nobjs = []
        self.ntypes = []

        if xml is not None:
            self.parse(xml)
            return

        self.addresses = addresses
        self.nnames = nnames
        self.nparents = nparents
        self.nobjs = nobjs
        self.ntypes = ntypes

    def __str__(self):
        """Return string representation of the nodes/folders/groups."""
        if self.root is None:
            return "Folder <root>"
        ind = self.addresses.index(self.root)
        if self.ntypes[ind] == TAG_FOLDER:
            return f"Folder ({self.root})"
        if self.ntypes[ind] == TAG_GROUP:
            return f"Group ({self.root})"
        return f"Node ({self.root})"

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
        out = (
            f"{self}\n"
            f"{self.__repr_folders__(folders)}"
            f"{self.__repr_groups__(groups)}"
            f"{self.__repr_nodes__(nodes)}"
        )
        return out

    def __repr_folders__(self, folders):
        """Return a representation of the folder structure."""
        out = ""
        for fold in folders:
            fold_obj = self[fold[2]]
            out += f"  + {fold[1]}: Folder({fold[2]})\n"
            for line in repr(fold_obj).split("\n")[1:]:
                out += f"  |   {line}\n"
            out += "  -\n"
        return out

    def __repr_groups__(self, groups):
        """Return a representation of the groups structure."""
        out = ""
        for group in groups:
            out += f"  + {group[1]}: Group({group[2]})\n"
            for member in self[group[2]].members:
                out += f"  |  {self[member].name}: Node({member})\n"
            out += "  |\n  -\n"
        return out

    def __repr_nodes__(self, nodes):
        """Return a representation of the nodes structure."""
        out = ""
        for node in nodes:
            has_children = node[2] in self.nparents
            out += f"  {'+ ' if has_children else ''}{node[1]}: Node({node[2]})\n"
            if has_children:
                for child in self.get_children(node[2]):
                    out += f"  |   {child[1]}: Node({child[2]})\n"
                out += "  |\n  -\n"
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
        address = value_from_xml(xmldoc, TAG_NODE)

        node = self.get_by_id(address)
        if not node:
            _LOGGER.debug(
                "Received a node update for node %s but could not find a record of this "
                "node. Please try restarting the module if the problem persists, this "
                "may be due to a new node being added to the ISY since last restart.",
                address,
            )
            return
        value = value_from_xml(xmldoc, ATTR_ACTION, "")
        value = int(value) if value != "" else ISY_VALUE_UNKNOWN
        prec = attr_from_xml(xmldoc, ATTR_ACTION, ATTR_PRECISION, DEFAULT_PRECISION)
        uom = attr_from_xml(
            xmldoc, ATTR_ACTION, ATTR_UNIT_OF_MEASURE, DEFAULT_UNIT_OF_MEASURE
        )
        formatted = value_from_xml(xmldoc, TAG_FORMATTED)

        # Process the action and value if provided in event data.
        node.update_state(
            NodeProperty(PROP_STATUS, value, prec, uom, formatted, address)
        )
        _LOGGER.debug("ISY Updated Node: " + address)

    def control_message_received(self, xmldoc):
        """
        Pass Control events from an event stream message to nodes.

        Used for sending out to subscribers.
        """
        address = value_from_xml(xmldoc, TAG_NODE)
        cntrl = value_from_xml(xmldoc, ATTR_CONTROL)
        if not (address and cntrl):
            # If there is no node associated with the control message ignore it
            return

        node = self.get_by_id(address)
        if not node:
            _LOGGER.debug(
                "Received a node update for node %s but could not find a record of this "
                "node. Please try restarting the module if the problem persists, this "
                "may be due to a new node being added to the ISY since last restart.",
                address,
            )
            return

        # Process the action and value if provided in event data.
        node.update_last_update()
        value = value_from_xml(xmldoc, ATTR_ACTION, 0)
        value = int(value) if value != "" else ISY_VALUE_UNKNOWN
        prec = attr_from_xml(xmldoc, ATTR_ACTION, ATTR_PRECISION, DEFAULT_PRECISION)
        uom = attr_from_xml(
            xmldoc, ATTR_ACTION, ATTR_UNIT_OF_MEASURE, DEFAULT_UNIT_OF_MEASURE
        )
        formatted = value_from_xml(xmldoc, TAG_FORMATTED)

        if cntrl == PROP_RAMP_RATE:
            value = INSTEON_RAMP_RATES.get(value, value)
            uom = UOM_SECONDS
        node_property = NodeProperty(cntrl, value, prec, uom, formatted, address)
        if (
            cntrl == PROP_COMMS_ERROR
            and value == 0
            and PROP_COMMS_ERROR in node.aux_properties
        ):
            # Clear a previous comms error
            del node.aux_properties[PROP_COMMS_ERROR]
        elif cntrl not in EVENT_PROPS_IGNORED:
            node.update_property(node_property)
        node.control_events.notify(node_property)
        _LOGGER.debug("ISY Node Control Event: %s", node_property)

    def node_changed_received(self, xmldoc):
        """Handle Node Change/Update events from an event stream message."""
        action = value_from_xml(xmldoc, ATTR_ACTION)
        if not action or action not in NODE_CHANGED_ACTIONS:
            return
        node = value_from_xml(xmldoc, TAG_NODE)
        if action == NC_NODE_ERROR:
            _LOGGER.error("ISY Could not communicate with device: %s", node)
        # FUTURE: Handle additional node change actions to force updates.

    def parse(self, xml):
        """
        Parse the xml data.

        |  xml: String of the xml data
        """
        try:
            xmldoc = minidom.parseString(xml)
        except XML_ERRORS:
            _LOGGER.error("%s: Nodes", XML_PARSE_ERROR)
            raise ISYResponseParseError(XML_PARSE_ERROR)

        # get nodes
        ntypes = [TAG_FOLDER, TAG_NODE, TAG_GROUP]
        for ntype in ntypes:
            features = xmldoc.getElementsByTagName(ntype)

            for feature in features:
                # Get Node Information
                address = value_from_xml(feature, TAG_ADDRESS)
                nname = value_from_xml(feature, TAG_NAME)
                nparent = value_from_xml(feature, TAG_PARENT)
                pnode = value_from_xml(feature, TAG_PRIMARY_NODE)
                family = value_from_xml(feature, TAG_FAMILY)
                device_type = value_from_xml(feature, TAG_TYPE)
                node_def_id = attr_from_element(feature, ATTR_NODE_DEF_ID)
                enabled = value_from_xml(feature, TAG_ENABLED) == XML_TRUE

                # Assume Insteon, update as confirmed otherwise
                protocol = PROTO_INSTEON
                zwave_props = None
                node_server = None
                if family is not None:
                    if family == FAMILY_ZWAVE:
                        protocol = PROTO_ZWAVE
                        zwave_props = ZWaveProperties(
                            feature.getElementsByTagName(TAG_DEVICE_TYPE)[0]
                        )
                    elif family in (FAMILY_BRULTECH, FAMILY_RCS):
                        protocol = PROTO_ZIGBEE
                    elif family == FAMILY_NODESERVER:
                        # Node Server Slot is stored with family as text:
                        node_server = attr_from_xml(feature, TAG_FAMILY, ATTR_INSTANCE)
                        if node_server:
                            protocol = f"{PROTO_NODE_SERVER}_{node_server}"

                # Process the different node types
                if ntype == TAG_FOLDER and address not in self.addresses:
                    self.insert(address, nname, nparent, None, ntype)
                elif ntype == TAG_NODE:
                    if address in self.addresses:
                        self.get_by_id(address).update(xmldoc=feature)
                        continue
                    state, aux_props = parse_xml_properties(feature)
                    self.insert(
                        address,
                        nname,
                        nparent,
                        Node(
                            self,
                            address=address,
                            name=nname,
                            state=state,
                            aux_properties=aux_props,
                            zwave_props=zwave_props,
                            node_def_id=node_def_id,
                            pnode=pnode,
                            device_type=device_type,
                            enabled=enabled,
                            node_server=node_server,
                            protocol=protocol,
                            family_id=family,
                        ),
                        ntype,
                    )
                elif ntype == TAG_GROUP and address not in self.addresses:
                    flag = attr_from_element(feature, ATTR_FLAG)
                    # Ignore groups that contain 0x08 in the flag since
                    # that is a ISY scene that contains every device/
                    # scene so it will contain some scenes we have not
                    # seen yet so they are not defined and it includes
                    # the ISY MAC address in newer versions of
                    # ISY firmwares > 5.0.6+ ..
                    if int(flag) & 0x08:
                        _LOGGER.debug("Skipping root group flag=%s %s", flag, address)
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
                        address,
                        nname,
                        nparent,
                        Group(
                            self,
                            address=address,
                            name=nname,
                            members=members,
                            controllers=controllers,
                            family_id=family,
                            pnode=pnode,
                        ),
                        ntype,
                    )
            _LOGGER.debug("ISY Loaded %s", ntype)

    async def update(self, wait_time=0, xml=None):
        """
        Update the status and properties of the nodes in the class.

        This calls the "/rest/status" endpoint.

        |  wait_time: [optional] Amount of seconds to wait before updating
        """
        if wait_time:
            await sleep(wait_time)

        if xml is None:
            xml = await self.isy.conn.get_status()

        if xml is None:
            _LOGGER.warning("ISY Failed to update nodes.")
            return

        try:
            xmldoc = minidom.parseString(xml)
        except XML_ERRORS:
            _LOGGER.error("%s: Nodes", XML_PARSE_ERROR)
            return False

        for feature in xmldoc.getElementsByTagName(TAG_NODE):
            address = feature.attributes[ATTR_ID].value

            if address in self.addresses:
                await self.get_by_id(address).update(xmldoc=feature)
                continue

        _LOGGER.info("ISY Updated Node Statuses.")

    async def update_nodes(self, wait_time=0):
        """
        Update the contents of the class.

        This calls the "/rest/nodes" endpoint.

        |  wait_time: [optional] Amount of seconds to wait before updating
        """
        if wait_time:
            await sleep(wait_time)
        xml = await self.isy.conn.get_nodes()
        if xml is None:
            _LOGGER.warning("ISY Failed to update nodes.")
            return
        self.parse(xml)

    def insert(self, address, nname, nparent, nobj, ntype):
        """
        Insert a new node into the lists.

        |  address: node id
        |  nname: node name
        |  nparent: node parent
        |  nobj: node object
        |  ntype: node type
        """
        self.addresses.append(address)
        self.nnames.append(nname)
        self.nparents.append(nparent)
        self.ntypes.append(ntype)
        self.nobjs.append(nobj)

    def __getitem__(self, val):
        """Navigate through the node tree. Can take names or IDs."""
        try:
            self.addresses.index(val)
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
        raise KeyError(f"Unrecognized Key: [{val}]")

    def __setitem__(self, item, value):
        """Set item value."""
        return None

    def get_by_name(self, val):
        """
        Get child object with the given name.

        |  val: String representing name to look for.
        """
        for i in range(len(self.addresses)):
            if (self.root is None or self.nparents[i] == self.root) and self.nnames[
                i
            ] == val:
                return self.get_by_index(i)
        return None

    def get_by_id(self, address):
        """
        Get object with the given ID.

        |  address: Integer representing node/group/folder id.
        """
        try:
            i = self.addresses.index(address)
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
            self.addresses[i],
            self.addresses,
            self.nnames,
            self.nparents,
            self.nobjs,
            self.ntypes,
        )

    def get_folder(self, address):
        """Return the folder of a given node address."""
        parent = self.nparents[self.addresses.index(address)]
        if parent is None:
            # Node is in the root folder.
            return None
        parent_index = self.addresses.index(parent)
        if self.ntypes[parent_index] != TAG_FOLDER:
            return self.get_folder(parent)
        return self.nnames[parent_index]

    @property
    def children(self):
        """Return the children of the class."""
        return self.get_children()

    def get_children(self, ident=None):
        """Return the children of the class."""
        if ident is None:
            ident = self.root
        out = [
            (self.ntypes[i], self.nnames[i], self.addresses[i])
            for i in [
                index for index, parent in enumerate(self.nparents) if parent == ident
            ]
        ]
        return out

    @property
    def has_children(self):
        """Return if the root has children."""
        return self.root in self.nparents

    @property
    def name(self):
        """Return the name of the root."""
        if self.root is None:
            return ""
        ind = self.addresses.index(self.root)
        return self.nnames[ind]

    @property
    def all_lower_nodes(self):
        """Return all nodes below the current root."""
        output = []
        myname = self.name + "/"

        for dtype, name, ident in self.children:
            if dtype in [TAG_GROUP, TAG_NODE]:
                output.append((dtype, myname + name, ident))
                if dtype == TAG_NODE and ident in self.nparents:
                    output += [
                        (child[0], f"{myname}{name}/{child[1]}", child[2])
                        for child in self.get_children(ident)
                    ]
            if dtype == TAG_FOLDER:
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
