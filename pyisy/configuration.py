"""ISY Configuration Lookup."""
from xml.dom import minidom

from .constants import (
    _LOGGER,
    ATTR_DESC,
    ATTR_ID,
    TAG_DESC,
    TAG_FEATURE,
    TAG_FIRMWARE,
    TAG_INSTALLED,
    TAG_NAME,
    TAG_NODE_DEFS,
    TAG_PRODUCT,
    TAG_ROOT,
    TAG_VARIABLES,
    XML_TRUE,
)
from .exceptions import XML_ERRORS, XML_PARSE_ERROR, ISYResponseParseError
from .helpers import value_from_nested_xml, value_from_xml


class Configuration(dict):
    """
    ISY Configuration class.

    DESCRIPTION:
        This class handles the ISY configuration.

    USAGE:
        This object may be used in a similar way as a
        dictionary with the either module names or ids
        being used as keys and a boolean indicating
        whether the module is installed will be
        returned. With the exception of 'firmware' and 'uuid',
        which will return their respective values.

    PARAMETERS:
        Portal Integration - Check-it.ca
        Gas Meter
        SEP ESP
        Water Meter
        Z-Wave
        RCS Zigbee Device Support
        Irrigation/ETo Module
        Electricity Monitor
        AMI Electricity Meter
        URL
        A10/X10 for INSTEON
        Portal Integration - GreenNet.com
        Networking Module
        OpenADR
        Current Cost Meter
        Weather Information
        Broadband SEP Device
        Portal Integration - BestBuy.com
        Elk Security System
        Portal Integration - MobiLinc
        NorthWrite NOC Module

    EXAMPLE:
        # configuration['Networking Module']
        True
        # configuration['21040']
        True

    """

    def __init__(self, xml=None):
        """
        Initialize configuration class.

        xml: String of xml data containing the configuration data
        """
        super().__init__()

        if xml is not None:
            self.parse(xml)

    def parse(self, xml):
        """
        Parse the xml data.

        xml: String of the xml data
        """
        try:
            xmldoc = minidom.parseString(xml)
        except XML_ERRORS:
            _LOGGER.error("%s: Configuration", XML_PARSE_ERROR)
            raise ISYResponseParseError(XML_PARSE_ERROR)

        self["firmware"] = value_from_xml(xmldoc, TAG_FIRMWARE)
        self["uuid"] = value_from_nested_xml(xmldoc, [TAG_ROOT, ATTR_ID])
        self["name"] = value_from_nested_xml(xmldoc, [TAG_ROOT, TAG_NAME])
        self["model"] = value_from_nested_xml(xmldoc, [TAG_PRODUCT, TAG_DESC], "ISY")
        self["variables"] = bool(value_from_xml(xmldoc, TAG_VARIABLES) == XML_TRUE)
        self["nodedefs"] = bool(value_from_xml(xmldoc, TAG_NODE_DEFS) == XML_TRUE)

        features = xmldoc.getElementsByTagName(TAG_FEATURE)
        for feature in features:
            idnum = value_from_xml(feature, ATTR_ID)
            desc = value_from_xml(feature, ATTR_DESC)
            installed_raw = value_from_xml(feature, TAG_INSTALLED)
            installed = bool(installed_raw == XML_TRUE)
            self[idnum] = installed
            self[desc] = self[idnum]

        _LOGGER.info("ISY Loaded Configuration")
