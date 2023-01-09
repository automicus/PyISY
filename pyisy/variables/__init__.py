"""ISY Variables."""
from asyncio import sleep
from xml.dom import minidom

from dateutil import parser

from ..constants import (
    ATTR_ID,
    ATTR_INIT,
    ATTR_PRECISION,
    ATTR_TS,
    ATTR_VAL,
    ATTR_VAR,
    TAG_NAME,
    TAG_TYPE,
    TAG_VARIABLE,
)
from ..exceptions import XML_ERRORS, XML_PARSE_ERROR, ISYResponseParseError
from ..helpers import attr_from_element, attr_from_xml, now, value_from_xml
from ..logging import _LOGGER
from .variable import Variable

EMPTY_VARIABLE_RESPONSES = [
    "/CONF/INTEGER.VAR not found",
    "/CONF/STATE.VAR not found",
    '<CList type="VAR_INT"></CList>',
]


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

        self.vids = {1: [], 2: []}
        self.vobjs = {1: {}, 2: {}}
        self.vnames = {1: {}, 2: {}}

        if vids is not None and vnames is not None and vobjs is not None:
            self.vids = vids
            self.vnames = vnames
            self.vobjs = vobjs
            return

        valid_definitions = False
        if def_xml is not None:
            valid_definitions = self.parse_definitions(def_xml)
        if valid_definitions and var_xml is not None:
            self.parse(var_xml)
        else:
            _LOGGER.warning("No valid variables defined")

    def __str__(self):
        """Return a string representation of the variable manager."""
        if self.root is None:
            return "Variable Collection"
        return f"Variable Collection (Type: {self.root})"

    def __repr__(self):
        """Return a string representing the children variables."""
        if self.root is None:
            return repr(self[1]) + repr(self[2])
        out = str(self) + "\n"
        for child in self.children:
            out += f"  {child[1]}: Variable({child[2]})\n"
        return out

    def parse_definitions(self, xmls):
        """Parse the XML Variable Definitions from the ISY."""
        valid_definitions = False
        for ind in range(2):
            # parse definitions
            if xmls[ind] is None or xmls[ind] in EMPTY_VARIABLE_RESPONSES:
                # No variables of this type defined.
                _LOGGER.info("No Type %s variables defined", ind + 1)
                continue
            try:
                xmldoc = minidom.parseString(xmls[ind])
            except XML_ERRORS:
                _LOGGER.error("%s: Type %s Variables", XML_PARSE_ERROR, ind + 1)
                continue
            else:
                features = xmldoc.getElementsByTagName(TAG_VARIABLE)
                for feature in features:
                    vid = int(attr_from_element(feature, ATTR_ID))
                    self.vnames[ind + 1][vid] = attr_from_element(feature, TAG_NAME)
                valid_definitions = True
        return valid_definitions

    def parse(self, xml):
        """Parse XML from the controller with details about the variables."""
        try:
            xmldoc = minidom.parseString(xml)
        except XML_ERRORS as exc:
            _LOGGER.error("%s: Variables", XML_PARSE_ERROR)
            raise ISYResponseParseError(XML_PARSE_ERROR) from exc

        features = xmldoc.getElementsByTagName(ATTR_VAR)
        for feature in features:
            vid = int(attr_from_element(feature, ATTR_ID))
            vtype = int(attr_from_element(feature, TAG_TYPE))
            init = value_from_xml(feature, ATTR_INIT)
            prec = int(value_from_xml(feature, ATTR_PRECISION, 0))
            val = value_from_xml(feature, ATTR_VAL)
            ts_raw = value_from_xml(feature, ATTR_TS)
            timestamp = parser.parse(ts_raw)
            vname = self.vnames[vtype].get(vid, "")

            vobj = self.vobjs[vtype].get(vid)
            if vobj is None:
                vobj = Variable(self, vid, vtype, vname, init, val, timestamp, prec)
                self.vids[vtype].append(vid)
                self.vobjs[vtype][vid] = vobj
            else:
                vobj.init = init
                vobj.status = val
                vobj.prec = prec
                vobj.last_edited = timestamp

        _LOGGER.info("ISY Loaded Variables")

    async def update(self, wait_time=0):
        """
        Update the variable objects with data from the controller.

        |  wait_time: Seconds to wait before updating.
        """
        await sleep(wait_time)
        xml = await self.isy.conn.get_variables()
        if xml is not None:
            self.parse(xml)
        else:
            _LOGGER.warning("ISY Failed to update variables.")

    def update_received(self, xmldoc):
        """Process an update received from the event stream."""
        xml = xmldoc.toxml()
        vtype = int(attr_from_xml(xmldoc, ATTR_VAR, TAG_TYPE))
        vid = int(attr_from_xml(xmldoc, ATTR_VAR, ATTR_ID))
        try:
            vobj = self.vobjs[vtype][vid]
        except KeyError:
            return  # this is a new variable that hasn't been loaded

        vobj.last_update = now()
        if f"<{ATTR_INIT}>" in xml:
            vobj.init = int(value_from_xml(xmldoc, ATTR_INIT))
        else:
            vobj.status = int(value_from_xml(xmldoc, ATTR_VAL))
            vobj.prec = int(value_from_xml(xmldoc, ATTR_PRECISION, 0))
            vobj.last_edited = parser.parse(value_from_xml(xmldoc, ATTR_TS))

        _LOGGER.debug("ISY Updated Variable: %s.%s", str(vtype), str(vid))

    def __getitem__(self, val):
        """
        Navigate through the variables by ID or name.

        |  val: Name or ID for navigation.
        """
        if self.root is None:
            if val in [1, 2]:
                return Variables(self.isy, val, self.vids, self.vnames, self.vobjs)
            raise KeyError(f"Unknown variable type: {val}")
        if isinstance(val, int):
            try:
                return self.vobjs[self.root][val]
            except (ValueError, KeyError) as err:
                raise KeyError(f"Unrecognized variable id: {val}") from err

        for vid, vname in self.vnames[self.root]:
            if vname == val:
                return self.vobjs[self.root][vid]
        raise KeyError(f"Unrecognized variable name: {val}")

    def __setitem__(self, val, value):
        """Handle the setitem function for the Class."""
        return None

    def get_by_name(self, val):
        """
        Get a variable with the given name.

        |  val: The name of the variable to look for.
        """
        vtype, _, vid = next(item for item in self.children if val in item)
        if not vid and vtype:
            raise KeyError(f"Unrecognized variable name: {val}")
        return self.vobjs[vtype].get(vid)

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
