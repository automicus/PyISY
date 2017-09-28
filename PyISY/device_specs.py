from xml.dom import minidom


class device_specs(dict):

    def __init__(self, parent, xml=None):
        """
        Initiates configuration class.

        parent: ISY class
        xml: String of xml data containing the configuration data
        """
        super(device_specs, self).__init__()
        self.parent = parent

        if xml is not None:
            self.parse(xml)

    def parse(self, xml):
        """
        Parses the xml data.

        xml: String of the xml data
        """
        xmldoc = minidom.parseString(xml)
        specs = xmldoc.getElementsByTagName('deviceSpecs')[0] # type: minidom.Element

        for spec in specs.childNodes: # type: minidom.Element
            if spec.nodeType == minidom.Element.ELEMENT_NODE:
                name = spec.tagName
                value = spec.childNodes[0].data
                self[name] = value

        self.parent.log.info('ISY Loaded Device Specs')

