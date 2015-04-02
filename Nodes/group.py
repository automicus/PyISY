from ..constants import _change2update_interval


class Group(object):

    """
    Group class

    DESCRIPTION:
        This class insteracts with ISY groups (scenes).

    METHODS:
        off()
        on()
    """

    def __init__(self, parent, nid):
        self.parent = parent
        self._id = nid
        self.dimmable = True

    def __str__(self):
        return 'Group(' + self._id + ')'

    def off(self):
        """Turns off all the nodes in a scene."""
        response = self.parent.parent.conn.nodeOff(self._id)

        if response is None:
            self.parent.parent.log.warning('ISY could not turn off scene: ' +
                                           self._id)
        else:
            self.parent.parent.log.info('ISY turned off scene: ' + self._id)
            self.parent.update(_change2update_interval)

    def on(self):
        """Turns on all the nodes in the scene to the set values."""
        response = self.parent.parent.conn.nodeOn(self._id, None)

        if response is None:
            self.parent.parent.log.warning('ISY could not turn on scene: ' +
                                           self._id)
        else:
            self.parent.parent.log.info('ISY turned on scene: ' + self._id)
            self.parent.update(_change2update_interval)
