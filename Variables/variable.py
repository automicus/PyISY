from ..constants import _change2update_interval
from ..constants import _empty_time
from VarEvents import Property


class Variable(object):

    init = Property(0)
    val = Property(0)
    lastEdit = Property(_empty_time, readonly=True)

    def __init__(self, parent, vid, vtype, init, val, ts):
        super(Variable, self).__init__()
        self.noupdate = False
        self.parent = parent
        self._id = vid
        self._type = vtype

        self.init.update(init, force=True, silent=True)
        self.init.reporter = self.__report_init__
        self.val.update(val, force=True, silent=True)
        self.val.reporter = self.__report_val__
        self.lastEdit.update(ts, force=True, silent=True)

    def __str__(self):
        return 'Variable(type=' + str(self._type) + ', id=' + str(self._id) \
            + ', val=' + str(self.val) + ')'

    def __repr__(self):
        return str(self)

    def __report_init__(self, val):
        self.noupdate = True
        self.setInit(val)
        self.noupdate = False

    def __report_val__(self, val):
        self.noupdate = True
        self.setValue(val)
        self.noupdate = False

    def update(self, waitTime=0):
        if not self.noupdate:
            self.parent.update(waitTime)

    def setInit(self, val):
        response = self.parent.parent.conn.initVariable(self._type,
                                                        self._id, val)
        if response is None:
            self.parent.parent.log.warning('ISY could not set variable init '
                                           + 'value: ' + str(self._type) + ', '
                                           + str(self._id))
        else:
            self.parent.parent.log.info('ISY set variable init value: '
                                        + str(self._type) + ', '
                                        + str(self._id))
            self.update(_change2update_interval)

    def setValue(self, val):
        response = self.parent.parent.conn.setVariable(self._type,
                                                       self._id, val)
        if response is None:
            self.parent.parent.log.warning('ISY could not set variable: '
                                           + str(self._type) + ', '
                                           + str(self._id))
        else:
            self.parent.parent.log.info('ISY set variable: ' + str(self._type)
                                        + ', ' + str(self._id))
            self.update(_change2update_interval)
