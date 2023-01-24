"""ISY Clock/Location Information."""
from __future__ import annotations

from asyncio import sleep
from dataclasses import dataclass
from datetime import date, datetime
import json
import time
from typing import TYPE_CHECKING

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
)
from pyisy.helpers.xml import parse_xml
from pyisy.logging import _LOGGER

if TYPE_CHECKING:
    from pyisy.isy import ISY

URL_CLOCK = "time"
TRUE_STR = "true"
TAG_TZ_ID = "TzId"


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
    tz_name: str | None = None

    @classmethod
    def from_xml(cls, xml_dict: dict[str, str]) -> ClockData:
        """Return a ISY Clock class from an xml DOM object."""
        tz_offset = float(xml_dict[TAG_TZ_OFFSET])
        return ClockData(
            tz_offset=round(tz_offset / 3600, 1)
            if (-12 > tz_offset > 12)  # Old firmware used seconds not hours
            else tz_offset,
            dst=xml_dict[TAG_DST] == TRUE_STR,
            latitude=float(xml_dict[TAG_LATITUDE]),
            longitude=float(xml_dict[TAG_LONGITUDE]),
            military=xml_dict[TAG_MILITARY_TIME] == TRUE_STR,
            last_called=ntp_to_system_time(int(xml_dict[TAG_NTP])),
            sunrise=ntp_to_system_time(int(xml_dict[TAG_SUNRISE])),
            sunset=ntp_to_system_time(int(xml_dict[TAG_SUNSET])),
            tz_name=xml_dict.get(TAG_TZ_ID),  # Only in newer firmware
        )


class Clock:
    """Class to update the ISY clock information."""

    isy: ISY
    loaded: bool = False
    clock_data: ClockData
    url: str

    def __init__(self, isy: ISY) -> None:
        """Initialize a new Clock Updater class."""
        self.isy = isy
        self.clock_data = ClockData()
        self.url = isy.conn.compile_url([URL_CLOCK])

    async def update(self, wait_time: float = 0) -> None:
        """
        Update the contents of the clock class.

        wait_time: [optional] Amount of seconds to wait before updating
        """
        await sleep(wait_time)
        xml_dict = parse_xml(await self.isy.conn.request(self.url), use_pp=False)
        if not (dt_dict := xml_dict["DT"]):
            return
        self.clock_data = ClockData.from_xml(dt_dict)
        _LOGGER.debug("Loaded clock information: %s", str(self))
        self.loaded = True

    async def update_thread(self, interval: float) -> None:
        """
        Continually update the class until it is told to stop.

        Should be run as a task in the event loop.
        """
        while self.isy.auto_update:
            await self.update(interval)

    def __str__(self) -> str:
        """Return string representation of Clock data."""
        return f"<ClockData: {json.dumps(self.clock_data.__dict__, sort_keys=True, default=str)}>"

    def __repr__(self) -> str:
        """Return string representation of Clock data."""
        return f"<ClockData: {json.dumps(self.clock_data.__dict__, sort_keys=True, default=str)}>"
