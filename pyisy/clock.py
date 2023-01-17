"""ISY Clock/Location Information."""
from __future__ import annotations

from asyncio import sleep
from dataclasses import dataclass
from datetime import date, datetime
import time
from typing import TYPE_CHECKING
from xml.dom import minidom

from pyisy.constants import (
    EMPTY_TIME,
    ISY_EPOCH_OFFSET,
    TAG_DST,
    TAG_LATITUDE,
    TAG_LONGITUDE,
    TAG_MILITARY_TIME,
    TAG_NTP,
    TAG_SUNRISE,
    TAG_SUNSET,
    TAG_TZ_OFFSET,
    XML_TRUE,
)
from pyisy.exceptions import (
    XML_ERRORS,
    XML_PARSE_ERROR,
    ISYResponseError,
    ISYResponseParseError,
)
from pyisy.helpers import value_from_xml
from pyisy.logging import _LOGGER

if TYPE_CHECKING:
    from pyisy.isy import ISY

URL_CLOCK = "time"


def ntp_to_system_time(timestamp: int) -> datetime:
    """Convert a ISY NTP time to system UTC time.

    Adapted from Python ntplib module.
    https://pypi.org/project/ntplib/

    Parameters:
    timestamp -- timestamp in NTP time

    Returns:
    corresponding system time

    Note: The ISY uses a EPOCH_OFFSET in addition to standard NTP.

    """
    _system_epoch = date(*time.gmtime(0)[0:3])
    _ntp_epoch = date(1900, 1, 1)
    ntp_delta = ((_system_epoch - _ntp_epoch).days * 24 * 3600) - ISY_EPOCH_OFFSET

    return datetime.fromtimestamp(timestamp - ntp_delta)


@dataclass
class ClockData:
    """
    Dataclass representing the ISY Clock Data.

    DESCRIPTION:
        This class handles the ISY clock/location info.

        Note: this module uses naive datetimes because the
        ISY is highly inconsistent with time conventions
        and does not present enough information to accurately
        manage DST without significant guessing and effort.

    ATTRIBUTES:
        isy: The ISY device class
        last_called: the time of the last call to /rest/time
        tz_offset: The Time Zone Offset of the ISY
        dst: Daylight Savings Time Enabled or not
        latitude: ISY Device Latitude
        longitude: ISY Device Longitude
        sunrise: ISY Calculated Sunrise
        sunset: ISY Calculated Sunset
        military: If the clock is military time or not.

    """

    last_called: datetime = EMPTY_TIME
    tz_offset: float = 0
    dst: bool = False
    latitude: float = 0.0
    longitude: float = 0.0
    sunrise: datetime = EMPTY_TIME
    sunset: datetime = EMPTY_TIME
    military: bool = False

    @classmethod
    def from_xml(cls, xmldoc: minidom.Element) -> ClockData:
        """Return a ISY Clock class from an xml DOM object."""
        tz_offset_sec = int(value_from_xml(xmldoc, TAG_TZ_OFFSET))
        return ClockData(
            tz_offset=round(tz_offset_sec / 3600, 1),
            dst=value_from_xml(xmldoc, TAG_DST) == XML_TRUE,
            latitude=float(value_from_xml(xmldoc, TAG_LATITUDE)),
            longitude=float(value_from_xml(xmldoc, TAG_LONGITUDE)),
            military=value_from_xml(xmldoc, TAG_MILITARY_TIME) == XML_TRUE,
            last_called=ntp_to_system_time(int(value_from_xml(xmldoc, TAG_NTP))),
            sunrise=ntp_to_system_time(int(value_from_xml(xmldoc, TAG_SUNRISE))),
            sunset=ntp_to_system_time(int(value_from_xml(xmldoc, TAG_SUNSET))),
        )


class Clock:
    """Class to update the ISY clock information."""

    __slots__ = ["isy", "clock_data", "url"]
    isy: ISY
    clock_data: ClockData
    url: str

    def __init__(self, isy: ISY) -> None:
        """Initialize a new Clock Updater class."""
        self.isy = isy
        self.clock_data = ClockData()
        self.url = isy.conn.compile_url([URL_CLOCK])

    async def update(self, wait_time: float = 0) -> None:
        """
        Update the contents of the networking class.

        wait_time: [optional] Amount of seconds to wait before updating
        """
        await sleep(wait_time)
        xml = await self.isy.conn.request(self.url)

        if not xml:
            raise ISYResponseError("Could not load clock information")

        try:
            xmldoc = minidom.parseString(xml)
        except XML_ERRORS as exc:
            raise ISYResponseParseError(XML_PARSE_ERROR) from exc

        self.clock_data = ClockData.from_xml(xmldoc)
        _LOGGER.debug("ISY loaded clock information")

    async def update_thread(self, interval: float) -> None:
        """
        Continually update the class until it is told to stop.

        Should be run as a task in the event loop.
        """
        while self.isy.auto_update:
            await self.update(interval)

    def __str__(self) -> str:
        """Return string representation of Clock data."""
        return str(self.clock_data)

    def __repr__(self) -> str:
        """Return string representation of Clock data."""
        return repr(self.clock_data)
