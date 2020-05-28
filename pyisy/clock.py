"""ISY Clock/Location Information."""
from asyncio import sleep
from xml.dom import minidom

from .constants import (
    _LOGGER,
    EMPTY_TIME,
    TAG_DST,
    TAG_LATITUDE,
    TAG_LONGITUDE,
    TAG_MILIATRY_TIME,
    TAG_NTP,
    TAG_SUNRISE,
    TAG_SUNSET,
    TAG_TZ_OFFSET,
    XML_TRUE,
)
from .exceptions import XML_ERRORS, XML_PARSE_ERROR, ISYResponseParseError
from .helpers import ntp_to_system_time, value_from_xml


class Clock:
    """
    ISY Clock class cobject.

    DESCRIPTION:
        This class handles the ISY clock/location info.

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

    def __init__(self, isy, xml=None):
        """
        Initialize the network resources class.

        isy: ISY class
        xml: String of xml data containing the configuration data
        """
        self.isy = isy
        self._last_called = EMPTY_TIME
        self._tz_offset = 0
        self._dst = False
        self._latitude = 0.0
        self._longitude = 0.0
        self._sunrise = EMPTY_TIME
        self._sunset = EMPTY_TIME
        self._military = False

        if xml is not None:
            self.parse(xml)

    def __str__(self):
        """Return a string representing the clock Class."""
        return f"ISY Clock (Last Updated {self.last_called})"

    def __repr__(self):
        """Return a long string showing all the clock values."""
        props = [
            name for name, value in vars(Clock).items() if isinstance(value, property)
        ]
        return "ISY Clock: {!r}".format(
            {prop: str(getattr(self, prop)) for prop in props}
        )

    def parse(self, xml):
        """
        Parse the xml data.

        xml: String of the xml data
        """
        try:
            xmldoc = minidom.parseString(xml)
        except XML_ERRORS:
            _LOGGER.error("%s: Clock", XML_PARSE_ERROR)
            raise ISYResponseParseError(XML_PARSE_ERROR)

        tz_offset_sec = int(value_from_xml(xmldoc, TAG_TZ_OFFSET))
        self._tz_offset = tz_offset_sec / 3600
        self._dst = value_from_xml(xmldoc, TAG_DST) == XML_TRUE
        self._latitude = float(value_from_xml(xmldoc, TAG_LATITUDE))
        self._longitude = float(value_from_xml(xmldoc, TAG_LONGITUDE))
        self._military = value_from_xml(xmldoc, TAG_MILIATRY_TIME) == XML_TRUE
        self._last_called = ntp_to_system_time(int(value_from_xml(xmldoc, TAG_NTP)))
        self._sunrise = ntp_to_system_time(int(value_from_xml(xmldoc, TAG_SUNRISE)))
        self._sunset = ntp_to_system_time(int(value_from_xml(xmldoc, TAG_SUNSET)))

        _LOGGER.info("ISY Loaded Clock Information")

    async def update(self, wait_time=0):
        """
        Update the contents of the networking class.

        wait_time: [optional] Amount of seconds to wait before updating
        """
        await sleep(wait_time)
        xml = await self.isy.conn.get_time()
        self.parse(xml)

    async def update_thread(self, interval):
        """
        Continually update the class until it is told to stop.

        Should be run as a task in the event loop.
        """
        while self.isy.auto_update:
            await self.update(interval)

    @property
    def last_called(self):
        """Get the time of the last call to /rest/time in UTC."""
        return self._last_called

    @property
    def tz_offset(self):
        """Provide the Time Zone Offset from the isy in Hours."""
        return self._tz_offset

    @property
    def dst(self):
        """Confirm if DST is enabled or not on the ISY."""
        return self._dst

    @property
    def latitude(self):
        """Provide the latitude information from the isy."""
        return self._latitude

    @property
    def longitude(self):
        """Provide the longitude information from the isy."""
        return self._longitude

    @property
    def sunrise(self):
        """Provide the sunrise information from the isy (UTC)."""
        return self._sunrise

    @property
    def sunset(self):
        """Provide the sunset information from the isy (UTC)."""
        return self._sunset

    @property
    def military(self):
        """Confirm if military time is in use or not on the isy."""
        return self._military
