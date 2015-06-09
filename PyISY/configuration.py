from xml.dom import minidom


class configuration(dict):

    """
    configuration class

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
        parent: The ISY device class
    """

    def __init__(self, parent, xml=None):
        """
        Initiates configuration class.

        parent: ISY class
        xml: String of xml data containing the configuration data
        """
        super(configuration, self).__init__()
        self.parent = parent

        if xml is not None:
            self.parse(xml)

    def parse(self, xml):
        """
        Parses the xml data.

        xml: String of the xml data
        """
        xmldoc = minidom.parseString(xml)
        features = xmldoc.getElementsByTagName('feature')

        for feature in features:
            idnum = feature.getElementsByTagName('id')[0].firstChild.toxml()
            desc = feature.getElementsByTagName('desc')[0].firstChild.toxml()
            installed_raw = feature.getElementsByTagName('isInstalled')[0] \
                .firstChild.toxml()
            installed = True if installed_raw == 'true' else False
            self[idnum] = installed
            self[desc] = self[idnum]

        self.parent.log.info('ISY Loaded Configuration')
