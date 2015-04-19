
from xml.dom import minidom
from time import sleep
from ISYtypes import MonitoredDict
from datetime import datetime

_thread_sleeptime = 30.0

class networking(object):

    """
    networking class

    DESCRIPTION:
        This class handles the ISY networking module.

    USAGE:
        This object may be used in a similar way as a
        dictionary with the either networking command
        names or ids being used as keys and the ISY
        networking command class will be returned.

    EXAMPLE:
        >>> a = networking['test function']
        >>> a.run()

    ATTRIBUTES:
        parent: The ISY device class
        nids: List of net command ids
        nnames: List of net command names
        nobjs: List of net command objects
    """

    nids = []
    nnames = []
    nobjs = []

    def __init__(self, parent, xml=None):
        """
        Initiates networking class.

        parent: ISY class
        xml: String of xml data containing the configuration data
        """
        self.parent = parent

        if xml is not None:
            self.parse(xml)

    def parse(self, xml):
        """
        Parses the xml data.

        xml: String of the xml data
        """
        try:
            xmldoc = minidom.parseString(xml)
        except:
            self.parent.log.error('ISY Could not parse networking commands, poorly formatted XML.')
        else:
            features = xmldoc.getElementsByTagName('NetRule')
            for feature in features:
                nid = int(feature.getElementsByTagName('id')[0].firstChild.toxml())
                if nid not in self.nids:
                    nname = feature.getElementsByTagName('name')[0].firstChild.toxml()
                    nobj = command(self, nid)
                    self.nids.append(nid)
                    self.nnames.append(nname)
                    self.nobjs.append(nobj)

            self.parent.log.info('ISY Loaded Networking Commands')

    def update(self, waitTime=0):
        """
        Updates the contents of the networking class

        waitTime: [optional] Amount of seconds to wait before updating
        """
        sleep(waitTime)
        xml = self.parent.conn.getNetwork()
        self.parse(xml)

    def updateThread(self):
        """
        Continually updates the class until it is told to stop.
        Should be run in a thread.
        """
        while self.parent.auto_update:
            self.update(_thread_sleeptime)

    def __getitem__(self, val):
        try:
            val = int(val)
            return self.getByID(val)
        except:
            return self.getByName(val)

    def __setitem__(self, val):
        return None

    def getByID(self, val):
        """
        Returns command object being given a command id

        val: Integer representing command id
        """
        try:
            ind = self.nids.index(val)
            return self.getByInd(ind)
        except:
            return None

    def getByName(self, val):
        """
        Returns command object being given a command name

        val: String representing command name
        """
        try:
            ind = self.nnames.index(val)
            return self.getByInd(ind)
        except:
            return None

    def getByInd(self, val):
        """
        Returns command object being given a command index

        val: Integer representing command index in List
        """
        return self.nobjs[val]

class command(object):

    """
    command class

    DESCRIPTION:
        This class handles individual networking commands.

    ATTRIBUTES:
        parent: The networking class
    """

    def __init__(self, parent, cid):
        """
        Initiates networking class.

        parent: ISY class
        cid: Integer of the command id
        """
        super(command, self).__init__()
        self.parent = parent
        self._id = cid

    def run(self):
        """
        Executes the networking command.
        """
        response = self.parent.parent.conn.runNetwork(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not run networking command: ' + str(self._id))
        else:
            self.parent.parent.log.info('ISY ran networking command: ' + str(self._id))
