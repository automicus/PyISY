from ..constants import _change2update_interval
from VarEvents import Property
from time import sleep
from xml.dom import minidom


class Node(object):

    """
    Node class

    DESCRIPTION:
        This class handles ISY nodes.

    ATTRIBUTES:
        parent: The nodes class
        status: The status of the node
    """

    status = Property(0)

    def __init__(self, parent, nid, nval, name, dimmable=True):
        self.parent = parent
        self._id = nid
        self.dimmable = dimmable
        self.name = name

        self.status = nval
        self.status.reporter = self.__report_status__

    def __str__(self):
        return 'Node(' + self._id + ')'

    def __report_status__(self, new_val):
        self.on(new_val)

    def update(self, waitTime=0, hint=None):
        if not self.parent.parent.auto_update:
            sleep(waitTime)
            xml = self.parent.parent.conn.updateNode(self._id)

            if xml is not None:
                try:
                    xmldoc = minidom.parseString(xml)
                except:
                    self.parent.parent.log.error('ISY Could not parse nodes,' +
                                                 'poorly formatted XML.')
                else:
                    new_st = int(xmldoc.getElementsByTagName('property')[0]
                                 .attributes['value'].value)
                    self.status.update(new_st, silent=True)
                    self.parent.parent.log.info('ISY updated node: ' +
                                                self._id)
            else:
                self.parent.parent.log.warning('ISY could not update node: ' +
                                               self._id)
        elif hint is not None:
            # assume value was set correctly, auto update will correct errors
            self.status.update(hint, silent=True)
            self.parent.parent.log.info('ISY updated node: ' + self._id)

    def off(self):
        response = self.parent.parent.conn.nodeOff(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not turn off node: ' +
                                           self._id)
        else:
            self.parent.parent.log.info('ISY turned off node: ' + self._id)
            self.update(_change2update_interval, hint=0)

    def on(self, val=None):
        response = self.parent.parent.conn.nodeOn(self._id, val)

        if response is None:
            self.parent.parent.log.warning('ISY could not turn on node: ' +
                                           self._id)
        else:
            if val is None:
                self.parent.parent.log.info('ISY turned on node: ' + self._id)
                val = 255
            else:
                self.parent.parent.log.info('ISY turned on node: ' + self._id +
                                            ', To value: ' + str(val))
                val = int(val)
            self.update(_change2update_interval, hint=val)

    def fastoff(self):
        response = self.parent.parent.conn.nodeFastOff(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not fast off node: ' +
                                           self._id)
        else:
            self.parent.parent.log.info('ISY turned did a fast off with node: '
                                        + self._id)
            self.update(_change2update_interval, hint=0)

    def faston(self):
        response = self.parent.parent.conn.nodeFastOn(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not fast on node: ' +
                                           self._id)
        else:
            self.parent.parent.log.info('ISY did a fast on with node: ' +
                                        self._id)
            self.update(_change2update_interval, hint=255)

    def bright(self):
        response = self.parent.parent.conn.nodeBright(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not brighten node: ' +
                                           self._id)
        else:
            self.parent.parent.log.info('ISY brightened node: ' + self._id)
            self.update(_change2update_interval)

    def dim(self):
        response = self.parent.parent.conn.nodeDim(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not dim node: ' +
                                           self._id)
        else:
            self.parent.parent.log.info('ISY dimmed node: ' + self._id)
            self.update(_change2update_interval)
