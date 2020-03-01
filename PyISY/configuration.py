"""ISY Configuration Lookup."""
from xml.dom import minidom

from .constants import ATTR_DESC, ATTR_ID
from .helpers import value_from_xml


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
        returned.

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
        >>> configuration['Networking Module']
        True
        >>> configuration['21040']
        True

    ATTRIBUTES:
        isy: The ISY device class

    """

    def __init__(self, isy, xml=None):
        """
        Initialize configuration class.

        isy: ISY class
        xml: String of xml data containing the configuration data
        """
        super().__init__()
        self.isy = isy

        if xml is not None:
            self.parse(xml)

    def parse(self, xml):
        """
        Parse the xml data.

        xml: String of the xml data
        """
        xmldoc = minidom.parseString(xml)
        features = xmldoc.getElementsByTagName("feature")

        for feature in features:
            idnum = value_from_xml(feature, ATTR_ID)
            desc = value_from_xml(feature, ATTR_DESC)
            installed_raw = value_from_xml(feature, "isInstalled")
            installed = bool(installed_raw == "true")
            self[idnum] = installed
            self[desc] = self[idnum]

        self.isy.log.info("ISY Loaded Configuration")
