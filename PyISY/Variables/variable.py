"""Manage variables from the ISY."""
from VarEvents import Property

from ..constants import EMPTY_TIME, UPDATE_INTERVAL


class Variable:
    """
    Object representing a variable on the controller.

    |  variables: The variable manager object.
    |  vid: List of variable IDs.
    |  vtype: List of variable types.
    |  init: List of values that variables initialize to when the controller
             starts.
    |  val: The current variable value.
    |  ts: The timestamp for the last time the variable was edited.

    :ivar init: Watched property that represents the value the variable
                initializes to when the controller boots.
    :ivar lastEdit: Watched property that indicates the last time the variable
                    was edited.
    :ivar val: Watched property that represents the value of the variable.
    """

    init = Property(0)
    val = Property(0)
    lastEdit = Property(EMPTY_TIME, readonly=True)

    def __init__(self, variables, vid, vtype, init, val, ts):
        """Initialize a Variable class."""
        super(Variable, self).__init__()
        self.noupdate = False
        self._variables = variables
        self.isy = variables.isy
        self._id = vid
        self._type = vtype

        self.init.update(init, force=True, silent=True)
        self.init.reporter = self.__report_init__
        self.val.update(val, force=True, silent=True)
        self.val.reporter = self.__report_val__
        self.lastEdit.update(ts, force=True, silent=True)

    def __str__(self):
        """Return a string representation of the variable."""
        return 'Variable(type={!s}, id={!s}, val={!s})'. \
            format(self._type, self._id, self.val)

    def __repr__(self):
        """Return a string representation of the variable."""
        return str(self)

    def __report_init__(self, val):
        """Report the init value for the variable."""
        self.noupdate = True
        self.setInit(val)
        self.noupdate = False

    def __report_val__(self, val):
        """Report the current value for the variable."""
        self.noupdate = True
        self.setValue(val)
        self.noupdate = False

    def update(self, wait_time=0):
        """
        Update the object with the variable's parameters from the controller.

        |  wait_time: Seconds to wait before updating.
        """
        if not self.noupdate:
            self._variables.update(wait_time)

    def setInit(self, val):
        """
        Set the initial value for the variable after the controller boots.

        |  val: The value to have the variable initialize to.
        """
        response = self.isy.conn.initVariable(self._type, self._id, val)
        if response is None:
            self.isy.log.warning('ISY could not set variable init value: '
                                 '%s.%s', str(self._type), str(self._id))
        else:
            self.isy.log.info('ISY set variable init value: %s.%s',
                              str(self._type), str(self._id))
            self.update(UPDATE_INTERVAL)

    def setValue(self, val):
        """
        Set the value of the variable.

        |  val: The value to set the variable to.
        """
        response = self.isy.conn.setVariable(self._type, self._id, val)
        if response is None:
            self.isy.log.warning('ISY could not set variable: %s.%s',
                                 str(self._type), str(self._id))
        else:
            self.isy.log.info('ISY set variable: %s.%s',
                              str(self._type), str(self._id))
            self.update(UPDATE_INTERVAL)
