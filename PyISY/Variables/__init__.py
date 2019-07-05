"""ISY Variables."""
from datetime import datetime
from time import sleep
from xml.dom import minidom

from ..constants import (ATTR_ID, ATTR_INIT, ATTR_NAME, ATTR_TS, ATTR_TYPE,
                         ATTR_VAL, ATTR_VAR, XML_PARSE_ERROR)
from ..helpers import attr_from_element, attr_from_xml, value_from_xml
from .variable import Variable


class Variables:
    """
    This class handles the ISY variables.

    This class can be used as a     dictionary to navigate through the
    controller's structure to objects of type
    :class:`~PyISY.Variables.Variable` that represent objects on the
    controller.

    |  isy: The ISY object.
    |  root: The ID of the current level of navigation.
    |  vids: List of variable IDs from the controller.
    |  vnames: List of variable names form the controller.
    |  vobjs: List of variable objects.
    |  vtypes: List of variable types.
    |  xml: XML string from the controller detailing the device's variables.

    :ivar children: List of the children below the current level of navigation.
    """

    vids = []
    vnames = []
    vobjs = []
    vtypes = []

    def __init__(self, isy, root=None, vids=None, vnames=None,
                 vobjs=None, vtypes=None, xml=None):
        """Initialize a Variables ISY Variable Manager class."""
        self.isy = isy
        self.root = root

        if vids is not None and vnames is not None \
                and vobjs is not None and vtypes is not None:
            self.vids = vids
            self.vnames = vnames
            self.vobjs = vobjs
            self.vtypes = vtypes

        elif xml is not None:
            self.parse(xml)

    def __str__(self):
        """Return a string representation of the variable manager."""
        if self.root is None:
            return 'Variable Collection'
        return 'Variable Collection (Type: {!s})'.format(self.root)

    def __repr__(self):
        """Return a string representing the children variables."""
        if self.root is None:
            return repr(self[1]) + repr(self[2])
        out = str(self) + '\n'
        for child in self.children:
            out += '  {!s}: Variable({!s})\n'.format(child[1], child[2])
        return out

    def parse(self, xmls):
        """Parse XML from the controller with details about the variables."""
        try:
            xmldocs = [minidom.parseString(xml) for xml in xmls]
        except:
            self.isy.log.error("%s: Variables", XML_PARSE_ERROR)
        else:
            # parse definitions
            for ind in range(2):
                features = xmldocs[ind].getElementsByTagName('e')
                for feature in features:
                    self.vids.append(int(attr_from_element(feature, ATTR_ID)))
                    self.vnames.append(attr_from_element(feature, ATTR_NAME))
                    self.vtypes.append(ind + 1)

            # parse values
            count = 0
            for ind in range(2, 4):
                features = xmldocs[ind].getElementsByTagName(ATTR_VAR)
                for feature in features:
                    init = value_from_xml(feature, ATTR_INIT)
                    val = value_from_xml(feature, ATTR_VAL)
                    ts_raw = value_from_xml(feature, ATTR_TS)
                    t_s = datetime.strptime(ts_raw, '%Y%m%d %H:%M:%S')
                    self.vobjs.append(Variable(self, self.vids[count], ind - 1,
                                               init, val, t_s))
                    count += 1

            self.isy.log.info('ISY Loaded Variables')

    def update(self, wait_time=0):
        """
        Update the variable objects with data from the controller.

        |  wait_time: Seconds to wait before updating.
        """
        sleep(wait_time)
        xml = self.isy.conn.updateVariables()
        # TODO: Combine Parse and Update functions.
        if xml is not None:
            try:
                xmldoc = minidom.parseString(xml)

                features = xmldoc.getElementsByTagName(ATTR_VAR)
                for feature in features:
                    vid = int(attr_from_element(feature, ATTR_ID))
                    vtype = int(attr_from_element(feature, ATTR_TYPE))
                    init = value_from_xml(feature, ATTR_INIT)
                    val = value_from_xml(feature, ATTR_VAL)
                    ts_raw = value_from_xml(feature, ATTR_TS)
                    t_s = datetime.strptime(ts_raw, '%Y%m%d %H:%M:%S')

                    vobj = self[vtype][vid]
                    if vobj is None:
                        vobj = Variable(self, vid, vtype, init, val, t_s)
                        self.vtypes.append(vtype)
                        self.vids.append(vid)
                        self.vnames.append('')
                        self.vobjs.append(vobj)
                    else:
                        vobj.init.update(init, force=True, silent=True)
                        vobj.val.update(val, force=True, silent=True)
                        vobj.lastEdit.update(t_s, force=True, silent=True)

            except:
                self.isy.log.warning('ISY Failed to update variables, '
                                     'recieved bad XML.')

        else:
            self.isy.log.warning('ISY Failed to update variables.')

    def _upmsg(self, xmldoc):
        xml = xmldoc.toxml()
        vtype = int(attr_from_xml(xmldoc, ATTR_VAR, ATTR_TYPE))
        vid = int(attr_from_xml(xmldoc, ATTR_VAR, ATTR_ID))
        try:
            vobj = self[vtype][vid]
        except KeyError:
            pass  # this is a new variable that hasn't been loaded
        else:

            if '<init>' in xml:
                vobj.init.update(int(value_from_xml(xmldoc, ATTR_INIT)),
                                 force=True, silent=True)
            else:
                vobj.val.update(int(value_from_xml(xmldoc, ATTR_VAL)),
                                force=True, silent=True)
                ts_raw = value_from_xml(xmldoc, ATTR_TS)
                vobj.lastEdit.update(datetime.strptime(ts_raw,
                                                       '%Y%m%d %H:%M:%S'),
                                     force=True, silent=True)
            self.isy.log.debug('ISY Updated Variable: %s', str(vid))

    def __getitem__(self, val):
        """
        Navigate through the variables by ID or name.

        |  val: Name or ID for navigation.
        """
        if self.root is None:
            if val in [1, 2]:
                return Variables(self.isy, val, self.vids, self.vnames,
                                 self.vobjs, self.vtypes)
            raise KeyError('Unknown variable type: {!s}'.format(val))
        if isinstance(val, int):
            search_arr = self.vids
        else:
            search_arr = self.vnames

        not_found = True
        ind = -1
        while not_found:
            try:
                ind = search_arr.index(val, ind + 1)
                if self.vtypes[ind] == self.root:
                    not_found = False
            except ValueError:
                break
        if not_found:
            raise KeyError('Unrecognized variable id: {!s}'.format(val))
        return self.vobjs[ind]

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
        for ind in range(len(self.vids)):
            if self.vtypes[ind] in types:
                out.append((self.vtypes[ind], self.vnames[ind],
                            self.vids[ind]))
        return out
