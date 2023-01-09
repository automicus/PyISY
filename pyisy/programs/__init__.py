"""Init for management of ISY Programs."""
import asyncio
from xml.dom import minidom

from dateutil import parser

from ..constants import (
    ATTR_ID,
    ATTR_PARENT,
    ATTR_STATUS,
    EMPTY_TIME,
    TAG_ENABLED,
    TAG_FOLDER,
    TAG_NAME,
    TAG_PRGM_FINISH,
    TAG_PRGM_RUN,
    TAG_PRGM_RUNNING,
    TAG_PRGM_STATUS,
    TAG_PROGRAM,
    UPDATE_INTERVAL,
    XML_OFF,
    XML_ON,
    XML_TRUE,
)
from ..exceptions import XML_ERRORS, XML_PARSE_ERROR
from ..helpers import attr_from_element, now, value_from_xml
from ..logging import _LOGGER
from ..nodes import NodeIterator as ProgramIterator
from .folder import Folder
from .program import Program


class Programs:
    """
    This class handles the ISY programs.

    This class can be used as a dictionary
    to navigate through the controller's structure to objects of type
    :class:`pyisy.programs.Program` and :class:`pyisy.programs.Folder`
    (when requested) that represent objects on the controller.

    |  isy: The ISY device class
    |  root: Program/Folder ID representing the current level of navigation.
    |  addresses: List of program and folder IDs.
    |  pnames: List of the program and folder names.
    |  pparents: List of the program and folder parent IDs.
    |  pobjs: List of program and folder objects.
    |  ptypes: List of the program and folder types.
    |  xml: XML string from the controller detailing the programs and folders.

    :ivar all_lower_programs: A list of all programs below the current
                            navigation level. Does not return folders.
    :ivar children: A list of the children immediately below the current
                    navigation level.
    :ivar leaf: The child object representing the current item in navigation.
                This is useful for getting a folder to act as a program.
    :ivar name: The name of the program at the current level of navigation.
    """

    def __init__(
        self,
        isy,
        root=None,
        addresses=None,
        pnames=None,
        pparents=None,
        pobjs=None,
        ptypes=None,
        xml=None,
    ):
        """Initialize the Programs ISY programs manager class."""
        self.isy = isy
        self.root = root

        self.addresses = []
        self.pnames = []
        self.pparents = []
        self.pobjs = []
        self.ptypes = []

        if xml is not None:
            self.parse(xml)
            return

        self.addresses = addresses
        self.pnames = pnames
        self.pparents = pparents
        self.pobjs = pobjs
        self.ptypes = ptypes

    def __str__(self):
        """Return a string representation of the program manager."""
        if self.root is None:
            return "Folder <root>"
        ind = self.addresses.index(self.root)
        if self.ptypes[ind] == TAG_FOLDER:
            return f"Folder ({self.root})"
        if self.ptypes[ind] == TAG_PROGRAM:
            return f"Program ({self.root})"
        return ""

    def __repr__(self):
        """Return a string showing the hierarchy of the program manager."""
        # get and sort children
        folders = []
        programs = []
        for child in self.children:
            if child[0] == TAG_FOLDER:
                folders.append(child)
            elif child[0] == TAG_PROGRAM:
                programs.append(child)

        # initialize data
        folders.sort(key=lambda x: x[1])
        programs.sort(key=lambda x: x[1])
        out = str(self) + "\n"

        # format folders
        for fold in folders:
            fold_obj = self[fold[2]]
            out += f"  + {fold[1]}: Folder({fold[2]})\n"
            for line in repr(fold_obj).split("\n")[1:]:
                out += f"  |   {line}\n"
            out += "  -\n"

        # format programs
        for prog in programs:
            out += f"  {prog[1]}: {self[prog[2]]}\n"

        return out

    def __iter__(self):
        """
        Return an iterator that iterates through all the programs.

        Does not iterate folders. Only Programs that are beneath the current
        folder in navigation.
        """
        iter_data = self.all_lower_programs
        return ProgramIterator(self, iter_data, delta=1)

    def __reversed__(self):
        """Return an iterator that goes in reverse order."""
        iter_data = self.all_lower_programs
        return ProgramIterator(self, iter_data, delta=-1)

    def update_received(self, xmldoc):
        """Update programs from EventStream message."""
        # pylint: disable=attribute-defined-outside-init
        xml = xmldoc.toxml()
        address = value_from_xml(xmldoc, ATTR_ID).zfill(4)
        try:
            pobj = self.get_by_id(address).leaf
        except ValueError:
            _LOGGER.warning(
                "ISY received program update for new program; reload the module to update"
            )
            return  # this is a new program that hasn't been registered

        if not isinstance(pobj, Program):
            return

        new_status = False

        if f"<{TAG_PRGM_STATUS}>" in xml:
            status = value_from_xml(xmldoc, TAG_PRGM_STATUS)
            if status == "21":
                pobj.ran_then += 1
                new_status = True
            elif status == "31":
                pobj.ran_else += 1

        if f"<{TAG_PRGM_RUN}>" in xml:
            pobj.last_run = parser.parse(value_from_xml(xmldoc, TAG_PRGM_RUN))

        if f"<{TAG_PRGM_FINISH}>" in xml:
            pobj.last_finished = parser.parse(value_from_xml(xmldoc, TAG_PRGM_FINISH))

        if XML_ON in xml or XML_OFF in xml:
            pobj.enabled = XML_ON in xml

        # Update Status last and make sure the change event fires, but only once.
        if pobj.status != new_status:
            pobj.status = new_status
        else:
            # Status didn't change, but something did, so fire the event.
            pobj.status_events.notify(new_status)

        _LOGGER.debug("ISY Updated Program: %s", address)

    def parse(self, xml):
        """
        Parse the XML from the controller and updates the state of the manager.

        xml: XML string from the controller.
        """
        try:
            xmldoc = minidom.parseString(xml)
        except XML_ERRORS:
            _LOGGER.error("%s: Programs, programs not loaded", XML_PARSE_ERROR)
            return

        plastup = now()

        # get nodes
        features = xmldoc.getElementsByTagName(TAG_PROGRAM)
        for feature in features:
            # id, name, and status
            address = attr_from_element(feature, ATTR_ID)
            pname = value_from_xml(feature, TAG_NAME)

            _LOGGER.debug("Parsing Program/Folder: %s [%s]", pname, address)

            pparent = attr_from_element(feature, ATTR_PARENT)
            pstatus = attr_from_element(feature, ATTR_STATUS) == XML_TRUE

            if attr_from_element(feature, TAG_FOLDER) == XML_TRUE:
                # folder specific parsing
                ptype = TAG_FOLDER
                data = {"pstatus": pstatus, "plastup": plastup}

            else:
                # program specific parsing
                ptype = TAG_PROGRAM

                # last run time
                plastrun = value_from_xml(feature, "lastRunTime", EMPTY_TIME)
                if plastrun != EMPTY_TIME:
                    plastrun = parser.parse(plastrun)

                # last finish time
                plastfin = value_from_xml(feature, "lastFinishTime", EMPTY_TIME)
                if plastfin != EMPTY_TIME:
                    plastfin = parser.parse(plastfin)

                # enabled, run at startup, running
                penabled = bool(attr_from_element(feature, TAG_ENABLED) == XML_TRUE)
                pstartrun = bool(attr_from_element(feature, "runAtStartup") == XML_TRUE)
                prunning = bool(attr_from_element(feature, TAG_PRGM_RUNNING) != "idle")

                # create data dictionary
                data = {
                    "pstatus": pstatus,
                    "plastrun": plastrun,
                    "plastfin": plastfin,
                    "penabled": penabled,
                    "pstartrun": pstartrun,
                    "prunning": prunning,
                    "plastup": plastup,
                }

            # add or update object if it already exists
            if address not in self.addresses:
                if ptype == TAG_FOLDER:
                    pobj = Folder(self, address, pname, **data)
                else:
                    pobj = Program(self, address, pname, **data)
                self.insert(address, pname, pparent, pobj, ptype)
            else:
                pobj = self.get_by_id(address).leaf
                asyncio.create_task(pobj.update(data=data))

        _LOGGER.info("ISY Loaded/Updated Programs")

    async def update(self, wait_time=UPDATE_INTERVAL, address=None):
        """
        Update the status of the programs and folders.

        |  wait_time: How long to wait before updating.
        |  address: The program ID to update.
        """
        await asyncio.sleep(wait_time)
        xml = await self.isy.conn.get_programs(address)

        if xml is not None:
            self.parse(xml)
        else:
            _LOGGER.warning("ISY Failed to update programs.")

    def insert(self, address, pname, pparent, pobj, ptype):
        """
        Insert a new program or folder into the manager.

        |  address: The ID of the program or folder.
        |  pname: The name of the program or folder.
        |  pparent: The parent of the program or folder.
        |  pobj: The object representing the program or folder.
        |  ptype: The type of the item being added (program/folder).
        """
        self.addresses.append(address)
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
            self.addresses.index(val)
            fun = self.get_by_id
        except ValueError:
            try:
                self.pnames.index(val)
                fun = self.get_by_name
            except ValueError:
                try:
                    val = int(val)
                    fun = self.get_by_index
                except (TypeError, ValueError) as err:
                    raise KeyError("Unrecognized Key: " + str(val)) from err

        try:
            return fun(val)
        except (ValueError, KeyError, IndexError):
            return None

    def __setitem__(self, val, value):
        """Set the item value."""
        return None

    def get_by_name(self, val):
        """
        Get a child program/folder with the given name.

        |  val: The name of the child program/folder to look for.
        """
        for i in range(len(self.addresses)):
            if (self.root is None or self.pparents[i] == self.root) and self.pnames[
                i
            ] == val:
                return self.get_by_index(i)
        return None

    def get_by_id(self, address):
        """
        Get a program/folder with the given ID.

        |  address: The program/folder ID to look for.
        """
        i = self.addresses.index(address)
        return self.get_by_index(i)

    def get_by_index(self, i):
        """
        Get the program/folder at the given index.

        |  i: The program/folder index.
        """
        if self.ptypes[i] == TAG_FOLDER:
            return Programs(
                self.isy,
                self.addresses[i],
                self.addresses,
                self.pnames,
                self.pparents,
                self.pobjs,
                self.ptypes,
            )
        return self.pobjs[i]

    @property
    def children(self):
        """Return the children of the class."""
        out = []
        for ind, name in enumerate(self.pnames):
            if self.pparents[ind] == self.root:
                out.append((self.ptypes[ind], name, self.addresses[ind]))
        return out

    @property
    def leaf(self):
        """Return the leaf property."""
        if self.root is not None:
            ind = self.addresses.index(self.root)
            if self.pobjs[ind] is not None:
                return self.pobjs[ind]
        return self

    @property
    def name(self):
        """Return the name of the path."""
        if self.root is not None:
            ind = self.addresses.index(self.root)
            return self.pnames[ind]
        return ""

    @property
    def all_lower_programs(self):
        """Return all lower programs in a path."""
        output = []
        myname = self.name + "/"

        for dtype, name, ident in self.children:
            if dtype == TAG_PROGRAM:
                output.append((dtype, myname + name, ident))

            else:
                output += [
                    (dtype2, myname + name2, ident2)
                    for (dtype2, name2, ident2) in self[ident].all_lower_programs
                ]
        return output
