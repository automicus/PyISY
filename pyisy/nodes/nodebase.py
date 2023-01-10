"""Base object for nodes and groups."""
from xml.dom import minidom

from ..constants import (
    ATTR_LAST_CHANGED,
    ATTR_LAST_UPDATE,
    ATTR_STATUS,
    CMD_BEEP,
    CMD_BRIGHTEN,
    CMD_DIM,
    CMD_DISABLE,
    CMD_ENABLE,
    CMD_FADE_DOWN,
    CMD_FADE_STOP,
    CMD_FADE_UP,
    CMD_OFF,
    CMD_OFF_FAST,
    CMD_ON,
    CMD_ON_FAST,
    COMMAND_FRIENDLY_NAME,
    METHOD_COMMAND,
    NODE_FAMILY_ID,
    TAG_ADDRESS,
    TAG_DESCRIPTION,
    TAG_IS_LOAD,
    TAG_LOCATION,
    TAG_NAME,
    TAG_SPOKEN,
    URL_CHANGE,
    URL_NODES,
    URL_NOTES,
    XML_TRUE,
)
from ..exceptions import XML_ERRORS, XML_PARSE_ERROR, ISYResponseParseError
from ..helpers import EventEmitter, NodeProperty, now, value_from_xml
from ..logging import _LOGGER


class NodeBase:
    """Base Object for Nodes and Groups/Scenes."""

    has_children = False

    def __init__(
        self,
        nodes,
        address,
        name,
        status,
        family_id=None,
        aux_properties=None,
        pnode=None,
        flag=0,
    ):
        """Initialize a Node Base class."""
        self._aux_properties = aux_properties if aux_properties is not None else {}
        self._family = NODE_FAMILY_ID.get(family_id)
        self._id = address
        self._name = name
        self._nodes = nodes
        self._notes = None
        self._primary_node = pnode
        self._flag = flag
        self._status = status
        self._last_update = now()
        self._last_changed = now()
        self.isy = nodes.isy
        self.status_events = EventEmitter()

    def __str__(self):
        """Return a string representation of the node."""
        return f"{type(self).__name__}({self._id})"

    @property
    def aux_properties(self):
        """Return the aux properties that were in the Node Definition."""
        return self._aux_properties

    @property
    def address(self):
        """Return the Node ID."""
        return self._id

    @property
    def description(self):
        """Return the description of the node from it's notes."""
        if self._notes is None:
            _LOGGER.debug(
                "No notes retrieved for node. Call get_notes() before accessing."
            )
        return self._notes[TAG_DESCRIPTION]

    @property
    def family(self):
        """Return the ISY Family category."""
        return self._family

    @property
    def flag(self):
        """Return the flag of the current node as a property."""
        return self._flag

    @property
    def folder(self):
        """Return the folder of the current node as a property."""
        return self._nodes.get_folder(self.address)

    @property
    def is_load(self):
        """Return the isLoad property of the node from it's notes."""
        if self._notes is None:
            _LOGGER.debug(
                "No notes retrieved for node. Call get_notes() before accessing."
            )
        return self._notes[TAG_IS_LOAD]

    @property
    def last_changed(self):
        """Return the UTC Time of the last status change for this node."""
        return self._last_changed

    @property
    def last_update(self):
        """Return the UTC Time of the last update for this node."""
        return self._last_update

    @property
    def location(self):
        """Return the location of the node from it's notes."""
        if self._notes is None:
            _LOGGER.debug(
                "No notes retrieved for node. Call get_notes() before accessing."
            )
        return self._notes[TAG_LOCATION]

    @property
    def name(self):
        """Return the name of the Node."""
        return self._name

    @property
    def primary_node(self):
        """Return just the parent/primary node address.

        This is similar to Node.parent_node but does not return the whole Node
        class, and will return itself if it is the primary node/group.

        """
        return self._primary_node

    @property
    def spoken(self):
        """Return the text of the Spoken property inside the group notes."""
        if self._notes is None:
            _LOGGER.debug(
                "No notes retrieved for node. Call get_notes() before accessing."
            )
        return self._notes[TAG_SPOKEN]

    @property
    def status(self):
        """Return the current node state."""
        return self._status

    @status.setter
    def status(self, value):
        """Set the current node state and notify listeners."""
        if self._status != value:
            self._status = value
            self._last_changed = now()
            self.status_events.notify(self.status_feedback)
        return self._status

    @property
    def status_feedback(self):
        """Return information for a status change event."""
        return {
            TAG_ADDRESS: self.address,
            ATTR_STATUS: self._status,
            ATTR_LAST_CHANGED: self._last_changed,
            ATTR_LAST_UPDATE: self._last_update,
        }

    async def get_notes(self):
        """Retrieve and parse the notes for a given node.

        Notes are not retrieved unless explicitly requested by
        a call to this function.
        """
        notes_xml = await self.isy.conn.request(
            self.isy.conn.compile_url([URL_NODES, self._id, URL_NOTES]), ok404=True
        )
        spoken = None
        is_load = None
        description = None
        location = None
        if notes_xml is not None and notes_xml != "":
            try:
                notes_dom = minidom.parseString(notes_xml)
            except XML_ERRORS as exc:
                _LOGGER.error("%s: Node Notes %s", XML_PARSE_ERROR, notes_xml)
                raise ISYResponseParseError() from exc

            spoken = value_from_xml(notes_dom, TAG_SPOKEN)
            location = value_from_xml(notes_dom, TAG_LOCATION)
            description = value_from_xml(notes_dom, TAG_DESCRIPTION)
            is_load = value_from_xml(notes_dom, TAG_IS_LOAD)
        return {
            TAG_SPOKEN: spoken,
            TAG_IS_LOAD: is_load == XML_TRUE,
            TAG_DESCRIPTION: description,
            TAG_LOCATION: location,
        }

    async def update(self, event=None, wait_time=0, xmldoc=None):
        """Update the group with values from the controller."""
        self.update_last_update()

    def update_property(self, prop):
        """Update an aux property for the node when received."""
        if not isinstance(prop, NodeProperty):
            _LOGGER.error("Could not update property value. Invalid type provided.")
            return
        self.update_last_update()

        aux_prop = self.aux_properties.get(prop.control)
        if aux_prop:
            if prop.uom == "" and not aux_prop.uom == "":
                # Guard against overwriting known UOM with blank UOM (ISYv4).
                prop.uom = aux_prop.uom
            if aux_prop == prop:
                return
        self.aux_properties[prop.control] = prop
        self.update_last_changed()
        self.status_events.notify(self.status_feedback)

    def update_last_changed(self, timestamp=None):
        """Set the UTC Time of the last status change for this node."""
        if timestamp is None:
            timestamp = now()
        self._last_changed = timestamp

    def update_last_update(self, timestamp=None):
        """Set the UTC Time of the last update for this node."""
        if timestamp is None:
            timestamp = now()
        self._last_update = timestamp

    async def send_cmd(self, cmd, val=None, uom=None, query=None):
        """Send a command to the device."""
        value = str(val) if val is not None else None
        _uom = str(uom) if uom is not None else None
        req = [URL_NODES, str(self._id), METHOD_COMMAND, cmd]
        if value:
            req.append(value)
        if _uom:
            req.append(_uom)
        req_url = self.isy.conn.compile_url(req, query)
        if not await self.isy.conn.request(req_url):
            _LOGGER.warning(
                "ISY could not send %s command to %s.",
                COMMAND_FRIENDLY_NAME.get(cmd),
                self._id,
            )
            return False
        _LOGGER.debug(
            "ISY command %s sent to %s.", COMMAND_FRIENDLY_NAME.get(cmd), self._id
        )
        return True

    async def beep(self):
        """Identify physical device by sound (if supported)."""
        return await self.send_cmd(CMD_BEEP)

    async def brighten(self):
        """Increase brightness of a device by ~3%."""
        return await self.send_cmd(CMD_BRIGHTEN)

    async def dim(self):
        """Decrease brightness of a device by ~3%."""
        return await self.send_cmd(CMD_DIM)

    async def disable(self):
        """Send command to the node to disable it."""
        if not await self.isy.conn.request(
            self.isy.conn.compile_url([URL_NODES, str(self._id), CMD_DISABLE])
        ):
            _LOGGER.warning("ISY could not %s %s.", CMD_DISABLE, self._id)
            return False
        return True

    async def enable(self):
        """Send command to the node to enable it."""
        if not await self.isy.conn.request(
            self.isy.conn.compile_url([URL_NODES, str(self._id), CMD_ENABLE])
        ):
            _LOGGER.warning("ISY could not %s %s.", CMD_ENABLE, self._id)
            return False
        return True

    async def fade_down(self):
        """Begin fading down (dim) a device."""
        return await self.send_cmd(CMD_FADE_DOWN)

    async def fade_stop(self):
        """Stop fading a device."""
        return await self.send_cmd(CMD_FADE_STOP)

    async def fade_up(self):
        """Begin fading up (dim) a device."""
        return await self.send_cmd(CMD_FADE_UP)

    async def fast_off(self):
        """Start manually brightening a device."""
        return await self.send_cmd(CMD_OFF_FAST)

    async def fast_on(self):
        """Start manually brightening a device."""
        return await self.send_cmd(CMD_ON_FAST)

    async def query(self):
        """Request the ISY query this node."""
        return await self.isy.query(address=self.address)

    async def turn_off(self):
        """Turn off the nodes/group in the ISY."""
        return await self.send_cmd(CMD_OFF)

    async def turn_on(self, val=None):
        """
        Turn the node on.

        |  [optional] val: The value brightness value (0-255) for the node.
        """
        if val is None or type(self).__name__ == "Group":
            cmd = CMD_ON
        elif int(val) > 0:
            cmd = CMD_ON
            val = str(val) if int(val) <= 255 else None
        else:
            cmd = CMD_OFF
            val = None
        return await self.send_cmd(cmd, val)

    async def rename(self, new_name):
        """
        Rename the node or group in the ISY.

        Note: Feature was added in ISY v5.2.0, this will fail on earlier versions.
        """

        # /rest/nodes/<nodeAddress>/change?name=<newName>
        req_url = self.isy.conn.compile_url(
            [URL_NODES, self._id, URL_CHANGE],
            query={TAG_NAME: new_name},
        )
        if not await self.isy.conn.request(req_url):
            _LOGGER.warning(
                "ISY could not update name for %s.",
                self._id,
            )
            return False
        _LOGGER.debug("ISY renamed %s to %s.", self._id, new_name)

        self._name = new_name
        return True
