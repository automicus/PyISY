from VarEvents import Property
from VarEvents import Var
from time import sleep
from xml.dom import minidom


class Climate(object):

    """
    climate class

    DESCRIPTION:
        This class handles the ISY climate module.

    PARAMETERS:
        Gust_Speed
        Temperature
        Temperature_Rate
        Rain_Rate
        Max_Rain_Rate
        Temperature_High
        Pressure_Rate
        Wind_Speed
        Elevation
        Dew_Point
        Wind_Average_Speed
        Pressure
        Gust_Direction
        Wind_Average_Direction
        Light
        Wind_Direction
        Humidity
        Humidity_Rate
        Rain_Today
        Light_Rate
        Water_Deficit_Yesterday
        Irrigation_Requirement
        Feels_Like
        Temperature_Low
        Evapotranspiration

    ATTRIBUTES:
        parent: The ISY device class
        *_units: Strings of the units used for each of the parameters.
    """

    # Values
    _id2name = ['Gust_Speed', 'Temperature', 'Temperature_Rate', 'Rain_Rate',
                'Max_Rain_Rate', 'Temperature_High', 'Pressure_Rate',
                'Wind_Speed', 'Elevation', 'Dew_Point', 'Wind_Average_Speed',
                'Pressure', 'Gust_Direction', 'Wind_Average_Direction',
                'Light', 'Wind_Direction', 'Humidity', 'Humidity_Rate',
                'Rain_Today', 'Light_Rate', 'Water_Deficit_Yesterday',
                'Irrigation_Requirement', 'Feels_Like', 'Temperature_Low',
                'Evapotranspiration']

    # value properties
    Gust_Speed = Property(0, readonly=True)
    Temperature = Property(0, readonly=True)
    Temperature_Rate = Property(0, readonly=True)
    Rain_Rate = Property(0, readonly=True)
    Max_Rain_Rate = Property(0, readonly=True)
    Temperature_High = Property(0, readonly=True)
    Pressure_Rate = Property(0, readonly=True)
    Wind_Speed = Property(0, readonly=True)
    Elevation = Property(0, readonly=True)
    Dew_Point = Property(0, readonly=True)
    Wind_Average_Speed = Property(0, readonly=True)
    Pressure = Property(0, readonly=True)
    Gust_Direction = Property(0, readonly=True)
    Wind_Average_Direction = Property(0, readonly=True)
    Light = Property(0, readonly=True)
    Wind_Direction = Property(0, readonly=True)
    Humidity = Property(0, readonly=True)
    Humidity_Rate = Property(0, readonly=True)
    Rain_Today = Property(0, readonly=True)
    Light_Rate = Property(0, readonly=True)
    Water_Deficit_Yesterday = Property(0, readonly=True)
    Irrigation_Requirement = Property(0, readonly=True)
    Feels_Like = Property(0, readonly=True)
    Temperature_Low = Property(0, readonly=True)
    Evapotranspiration = Property(0, readonly=True)

    # unit properties
    Gust_Speed_units = ''
    Temperature_units = ''
    Temperature_Rate_units = ''
    Rain_Rate_units = ''
    Max_Rain_Rate_units = ''
    Temperature_High_units = ''
    Pressure_Rate_units = ''
    Wind_Speed_units = ''
    Elevation_units = ''
    Dew_Point_units = ''
    Wind_Average_Speed_units = ''
    Pressure_units = ''
    Gust_Direction_units = ''
    Wind_Average_Direction_units = ''
    Light_units = ''
    Wind_Direction_units = ''
    Humidity_units = ''
    Humidity_Rate_units = ''
    Rain_Today_units = ''
    Light_Rate_units = ''
    Water_Deficit_Yesterday_units = ''
    Irrigation_Requirement_units = ''
    Feels_Like_units = ''
    Temperature_Low_units = ''
    Evapotranspiration_units = ''

    def __init__(self, parent, xml=None):
        """
        Initiates climate class.

        parent: ISY class
        xml: String of xml data containing the climate data
        """
        super(Climate, self).__init__()
        self.parent = parent
        self.parse(xml)

    def __str__(self):
        return 'Climate Module'

    def __repr__(self):
        out = 'Climate Module\n'
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if isinstance(attr, Var):
                units = getattr(self, attr_name + '_units')
                out += '  ' + attr_name + ' = ' + str(attr) \
                    + ' ' + units + '\n'
        return out

    def parse(self, xml):
        """
        Parses the xml data.

        xml: String of the xml data
        """
        try:
            xmldoc = minidom.parseString(xml)
        except:
            self.parent.log.error('ISY Could not parse climate, poorly '
                                  + 'formatted XML.')
        else:
            # parse definitions
            feature = xmldoc.getElementsByTagName('climate')[0]

            for node in feature.childNodes:
                (val, unit) = self._parse_val(node.firstChild.toxml())
                name = node.nodeName
                try:
                    prop = getattr(self, name)
                    prop.update(val, force=True, silent=True)
                    setattr(self, name + '_units', unit)
                except:
                    pass

            self.parent.log.info('ISY Loaded Environment Data')

    def _parse_val(self, val):
        try:
            # assume standard val unit combination
            (val, unit) = self._parse_val_num(val)
        except ValueError:
            # assume direction
            (val, unit) = self._parse_val_dir(val)
        return (val, unit)

    def _parse_val_num(self, val):
        split_val = val.split()
        if len(split_val) == 2:
            return (float(split_val[0]), split_val[1])
        else:
            # probably elevation, assume feet
            return (float(split_val[0]), 'feet')

    def _parse_val_dir(self, val):
        dirs = {'N': 0.,
                'NNE': 22.5,
                'NE': 45.,
                'ENE': 67.5,
                'E': 90.,
                'ESE': 112.5,
                'SE': 135.,
                'SSE': 157.5,
                'S': 180.,
                'SSW': 202.5,
                'SW': 225.,
                'WSW': 247.5,
                'W': 270.,
                'WNW': 292.5,
                'NW': 315.,
                'N/A': None}
        return (dirs[val], 'deg')

    def update(self, waitTime=0):
        """
        Updates the contents of the climate class

        waitTime: [optional] Amount of seconds to wait before updating
        """
        sleep(waitTime)
        xml = self.parent.conn.getClimate()
        self.parse(xml)

    def _upmsg(self, xml):
        xmldoc = minidom.parseString(xml)
        cid = int(xmldoc.getElementsByTagName('action')[0]
                  .firstChild.toxml()) - 1
        val_raw = xmldoc.getElementsByTagName('value')[0] \
            .firstChild.toxml().strip()
        unit_raw = xmldoc.getElementsByTagName('unit')[0].firstChild
        if unit_raw is not None:
            unit_raw = unit_raw.toxml().strip()
        else:
            unit_raw = ''
        (val, unit) = self._parse_val((val_raw + ' ' + unit_raw).strip())

        cname = self._id2name[cid]
        attr = getattr(self, cname)
        attr.update(val, force=True, silent=True)
        setattr(self, cname + '_units', unit)

        self.parent.log.debug('ISY Updated Climate Value: ' + cname)
