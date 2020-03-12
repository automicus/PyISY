"""ISY Variables."""
from datetime import datetime
from time import sleep
from xml.dom import minidom

from ..constants import (
    ATTR_ID,
    ATTR_INIT,
    ATTR_TS,
    ATTR_VAL,
    ATTR_VAR,
    TAG_NAME,
    TAG_TYPE,
    TAG_VARIABLE,
    XML_PARSE_ERROR,
    XML_STRPTIME,
)
from ..helpers import attr_from_element, attr_from_xml, value_from_xml
from .variable import Variable


class Variables:
    """
    This class handles the ISY variables.

    This class can be used as a     dictionary to navigate through the
    controller's structure to objects of type
    :class:`pyisy.variables.Variable` that represent objects on the
    controller.

    |  isy: The ISY object.
    |  root: The ID of the current level of navigation.
    |  vids: List of variable IDs from the controller.
    |  vnames: List of variable names form the controller.
    |  vobjs: List of variable objects.
    |  xml: XML string from the controller detailing the device's variables.

    :ivar children: List of the children below the current level of navigation.
    """

    vids = {1: [], 2: []}
    vobjs = {1: {}, 2: {}}
    vnames = {1: {}, 2: {}}

    def __init__(
        self,
        isy,
        root=None,
        vids=None,
        vnames=None,
        vobjs=None,
        def_xml=None,
        var_xml=None,
    ):
        """Initialize a Variables ISY Variable Manager class."""
        self.isy = isy
        self.root = root

        if vids is not None and vnames is not None and vobjs is not None:
            self.vids = vids
            self.vnames = vnames
            self.vobjs = vobjs
            return

        if def_xml is not None:
            self.parse_definitions(def_xml)
        if var_xml is not None:
            self.parse(var_xml)

    def __str__(self):
        """Return a string representation of the variable manager."""
        if self.root is None:
            return "Variable Collection"
        return "Variable Collection (Type: {!s})".format(self.root)

    def __repr__(self):
        """Return a string representing the children variables."""
        if self.root is None:
            return repr(self[1]) + repr(self[2])
        out = str(self) + "\n"
        for child in self.children:
            out += "  {!s}: Variable({!s})\n".format(child[1], child[2])
        return out

    def parse_definitions(self, xmls):
        """Parse the XML Variable Definitions from the ISY."""
        try:
            xmldocs = [minidom.parseString(xml) for xml in xmls]
        except (AttributeError, KeyError, ValueError, TypeError, IndexError):
            self.isy.log.error("%s: Variables", XML_PARSE_ERROR)
            return

        # parse definitions
        for ind in range(2):
            features = xmldocs[ind].getElementsByTagName(TAG_VARIABLE)
            for feature in features:
                vid = int(attr_from_element(feature, ATTR_ID))
                self.vnames[ind + 1][vid] = attr_from_element(feature, TAG_NAME)

    def parse(self, xml):
        """Parse XML from the controller with details about the variables."""
        try:
            xmldoc = minidom.parseString(xml)
        except (AttributeError, KeyError, ValueError, TypeError, IndexError):
            self.isy.log.error("%s: Variables", XML_PARSE_ERROR)
            return

        features = xmldoc.getElementsByTagName(ATTR_VAR)
        for feature in features:
            vid = int(attr_from_element(feature, ATTR_ID))
            vtype = int(attr_from_element(feature, TAG_TYPE))
            init = value_from_xml(feature, ATTR_INIT)
            val = value_from_xml(feature, ATTR_VAL)
            ts_raw = value_from_xml(feature, ATTR_TS)
            t_s = datetime.strptime(ts_raw, XML_STRPTIME)
            vname = self.vnames[vtype].get(vid, "")

            vobj = self.vobjs[vtype].get(vid)
            if vobj is None:
                vobj = Variable(self, vid, vtype, vname, init, val, t_s)
                self.vids[vtype].append(vid)
                self.vobjs[vtype][vid] = vobj
            else:
                vobj.init.update(init, force=True, silent=True)
                vobj.val.update(val, force=True, silent=True)
                vobj.lastEdit.update(t_s, force=True, silent=True)

        self.isy.log.info("ISY Loaded Variables")

    def update(self, wait_time=0):
        """
        Update the variable objects with data from the controller.

        |  wait_time: Seconds to wait before updating.
        """
        sleep(wait_time)
        xml = self.isy.conn.get_variables()
        self.parse(xml)

    def update_received(self, xmldoc):
        """Process an update received from the event stream."""
        xml = xmldoc.toxml()
        vtype = int(attr_from_xml(xmldoc, ATTR_VAR, TAG_TYPE))
        vid = int(attr_from_xml(xmldoc, ATTR_VAR, ATTR_ID))
        try:
            vobj = self.vobjs[vtype][vid]
        except KeyError:
            return  # this is a new variable that hasn't been loaded

        if f"<{ATTR_INIT}>" in xml:
            vobj.init.update(
                int(value_from_xml(xmldoc, ATTR_INIT)), force=True, silent=True
            )
        else:
            vobj.val.update(
                int(value_from_xml(xmldoc, ATTR_VAL)), force=True, silent=True
            )
            ts_raw = value_from_xml(xmldoc, ATTR_TS)
            vobj.lastEdit.update(
                datetime.strptime(ts_raw, XML_STRPTIME), force=True, silent=True
            )
        self.isy.log.debug("ISY Updated Variable: %s", str(vid))

    def __getitem__(self, val):
        """
        Navigate through the variables by ID or name.

        |  val: Name or ID for navigation.
        """
        if self.root is None:
            if val in [1, 2]:
                return Variables(self.isy, val, self.vids, self.vnames, self.vobjs)
            raise KeyError("Unknown variable type: {!s}".format(val))
        if isinstance(val, int):
            try:
                return self.vobjs[self.root][val]
            except (ValueError, KeyError):
                raise KeyError("Unrecognized variable id: {!s}".format(val))
        else:
            for vid, vname in self.vnames[self.root]:
                if vname == val:
                    return self.vobjs[self.root][vid]
            raise KeyError("Unrecognized variable name: {!s}".format(val))

    def __setitem__(self, val, value):
        """Handle the setitem function for the Class."""
        return None

    @property
    def children(self):
        """Get the children of the class."""
        if self.root is None:
            types = [1, 2]
        else:
            types = [self.root]

        out = []
        for vtype in types:
            for ind in range(len(self.vids[vtype])):
                out.append(
                    (
                        vtype,
                        self.vnames[vtype].get(self.vids[vtype][ind], ""),
                        self.vids[vtype][ind],
                    )
                )
        return out
