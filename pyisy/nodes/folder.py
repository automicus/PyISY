"""Folder object for nodes and groups."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from pyisy.constants import TAG_ADDRESS, TAG_NAME, URL_CHANGE, URL_NODES, Protocol
from pyisy.helpers.entity import Entity, EntityDetail
from pyisy.helpers.models import OptionalIntT
from pyisy.logging import _LOGGER

if TYPE_CHECKING:
    from pyisy.nodes import Nodes


@dataclass
class NodeFolderDetail(EntityDetail):
    """Dataclass for node folder details."""

    address: str = ""
    name: str = ""
    parent: dict[str, str] = field(default_factory=dict)
    flag: int = 0


class NodeFolder(Entity[NodeFolderDetail, OptionalIntT]):
    """Folder Object for Nodes and Groups/Scenes."""

    _status: OptionalIntT = 0
    _last_update: datetime
    _last_changed: datetime
    detail: NodeFolderDetail
    platform: Nodes

    def __init__(
        self, platform: Nodes, address: str, name: str, detail: NodeFolderDetail
    ):
        """Initialize a Node Folder class."""
        self.platform = platform
        self.isy = platform.isy
        self._address = address
        self._protocol = Protocol.NODE_FOLDER
        self._name = name
        self.detail = detail
        self._last_update = datetime.now()
        self._last_changed = datetime.now()

    @property
    def flag(self) -> int:
        """Return the flag of the current node as a property."""
        return self.detail.flag

    @property
    def folder(self) -> str | None:
        """Return the folder of the current node as a property.

        Returns a named tuple with (name, address)
        """
        return self.platform.get_folder(self.address)

    @property
    def parent(self) -> str | None:
        """Return just the parent address.

        This is similar to Node.parent_node but does not return the whole Node
        class, and will return itself if it is the primary node/group.

        """
        return self.detail.parent.get(TAG_ADDRESS, None)

    async def rename(self, new_name: str) -> bool:
        """
        Rename the node or group in the ISY.

        Note: Feature was added in ISY v5.2.0, this will fail on earlier versions.
        """
        # /rest/nodes/<nodeAddress>/change?name=<newName>
        req_url = self.isy.conn.compile_url(
            [URL_NODES, self.address, URL_CHANGE],
            query={TAG_NAME: new_name},
        )
        if not await self.isy.conn.request(req_url):
            _LOGGER.error(
                "Could not update name for %s.",
                self.address,
            )
            return False
        _LOGGER.debug("Renamed %s to %s.", self.address, new_name)

        self._name = new_name
        return True
