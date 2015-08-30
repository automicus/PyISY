from VarEvents import Property
from VarEvents import Var
from time import sleep
from xml.dom import minidom


class Climate(object):

    """
    This class handles the ISY climate module.

    |  parent: ISY class
    |  xml: String of xml data containing the climate data

    :ivar Gust_Speed: Watched Variable representing the gust speed.
    :ivar Temperature: Watched Variable representing the temperature.
    :ivar Temperature_Rate: Watched Variable representing the temperature rate.
    :ivar Rain_Rate: Watched Variable representing the rain rate.
    :ivar Max_Rain_Rate: Watched Variable representing the rain rate.
    :ivar Temperature_High: Watched Variable representing the high temperature.
    :ivar Pressure_Rate: Watched variable representing the pressure rate.
    :ivar Wind_Speed: Watched Variable representing the wind speed.
    :ivar Elevation: Watched Variable representing the elevation.
    :ivar Dew_Point: Watched Variable representing the dew point.
    :ivar Wind_Average_Speed: Watched Variable representing the avg wind speed.
    :ivar Pressure: Watched Variable representing the pressure.
    :ivar Gust_Direction: Watched Variable representing the gust direction.
    :ivar Wind_Average_Direction: Watched Variable representing the average wind
                                  direction.
    :ivar Light: Watched Variable representing the amount of light.
    :ivar Wind_Direction: Watched Variable representing the wind direction.
    :ivar Humidity: Watched Variable representing the humidity.
    :ivar Humidity_Rate: Watched Variable representing the humidity rate.
    :ivar Rain_Today: Watched Variable representing the forcast rain today.
    :ivar Light_Rate: Watched Variable representing the light rate.
    :ivar Water_Deficit_Yesterday: Watched Variable representing the water
                                   deficit yesterday.
    :ivar Irrigation_Requirement: Watched Variable representing the irrigation
                                  requirement.
    :ivar Feels_Like: Watched Variable representing the feels like temperature.
    :ivar Temperature_Low: Watched Variable representing the low temperature.
    :ivar Evapotranspiration: Watched Variable representing the
                              evapotranspiration amount.
    :ivar Gust_Speed_units: Gust speed units.
    :ivar Temperature_units: Temperature units.
    :ivar Temperature_Rate_units: Temperature rate units.
    :ivar Rain_Rate_units: Rain rate units.
    :ivar Max_Rain_Rate_units: Max rain rate units.
    :ivar Temperature_High_units: High temperature units.
    :ivar Pressure_Rate_units: Pressure rate units.
    :ivar Wind_Speed_units: Wind speed units.
    :ivar Elevation_units: Elevation units.
    :ivar Dew_Point_units: Dew point units.
    :ivar Wind_Average_Speed_units: Average wind speed units.
    :ivar Pressure_units: Pressure units.
    :ivar Gust_Direction_units: Gust direction units.
    :ivar Wind_Average_Direction_units: Average wind direction units.
    :ivar Light_units: Light amount units.
    :ivar Wind_Direction_units: Wind direction units.
    :ivar Humidity_units: Humidity units.
    :ivar Humidity_Rate_units: Humidity rate units.
    :ivar Rain_Today_units: Rain forecast units.
    :ivar Light_Rate_units: Light rate units.
    :ivar Water_Deficit_Yesterday_units: Water deficit units.
    :ivar Irrigation_Requirement_units: Irrigation requirement units.
    :ivar Feels_Like_units: Feels like temperature units.
    :ivar Temperature_Low_units: Low temperature units.
    :ivar Evapotranspiration_units: Evapotranspiration units.
    """

    # Values
    _id2name = ['Temperature', 'Temperature_High', 'Temperature_Low',
                'Feels_Like', 'Temperature_Average', 'Humidity', None,
                'Pressure', None, 'Dew_Point', 'Wind_Speed', None,
                'Wind_Direction', None, 'Gust_Speed', None, 'Total_Rain_Today',
                'Light', None, None, None, 'Evapotranspiration',
                'Irrigation_Requirement', 'Water_Deficit_Yesterday',
                'Elevation', None, None, None, None,
                'Average_Temperature_Tomorrow', 'High_Temperature_Tomorrow',
                'Low_Temperature_Tomorrow', 'Humidity_Tomorrow',
                'Wind_Speed_Tomorrow', 'Gust_Speed_Tomorrow', 'Rain_Tomorrow',
                'Snow_Tomorrow', None, None, None, None,
                'Forecast_Average_Temperature', 'Forecast_High_Temperature',
                'Forecast_Low_Temperature', 'Forecast_Humidity',
                'Forecast_Rain', 'Forecast_Snow', None, None, None, None]

    # value properties
    Temperature = Property(0, readonly=True)
    Temperature_High = Property(0, readonly=True)
    Temperature_Low = Property(0, readonly=True)
    Feels_Like = Property(0, readonly=True)
    Temperature_Average = Property(0, readonly=True)
    Humidity = Property(0, readonly=True)
    Pressure = Property(0, readonly=True)
    Dew_Point = Property(0, readonly=True)
    Wind_Speed = Property(0, readonly=True)
    Wind_Direction = Property(0, readonly=True)
    Gust_Speed = Property(0, readonly=True)
    Total_Rain_Today = Property(0, readonly=True)
    Light = Property(0, readonly=True)
    Evapotranspiration = Property(0, readonly=True)
    Irrigation_Requirement = Property(0, readonly=True)
    Water_Deficit_Yesterday = Property(0, readonly=True)
    Elevation = Property(0, readonly=True)
    # Coverage = Property(0, readonly=True)
    # Intensity = Property(0, readonly=True)
    # Weather_Condition = Property(0, readonly=True)
    # Cloud_Condition = Property(0, readonly=True)
    Average_Temperature_Tomorrow = Property(0, readonly=True)
    High_Temperature_Tomorrow = Property(0, readonly=True)
    Low_Temperature_Tomorrow = Property(0, readonly=True)
    Humidity_Tomorrow = Property(0, readonly=True)
    Wind_Speed_Tomorrow = Property(0, readonly=True)
    Gust_Speed_Tomorrow = Property(0, readonly=True)
    Rain_Tomorrow = Property(0, readonly=True)
    Snow_Tomorrow = Property(0, readonly=True)
    # Coverage_Tomorrow = Property(0, readonly=True)
    # Intensity_Tomorrow = Property(0, readonly=True)
    # Weather_Condition_Tomorrow = Property(0, readonly=True)
    # Cloud_Condition_Tomorrow = Property(0, readonly=True)
    Forecast_Average_Temperature = Property(0, readonly=True)
    Forecast_High_Temperature = Property(0, readonly=True)
    Forecast_Low_Temperature = Property(0, readonly=True)
    Forecast_Humidity = Property(0, readonly=True)
    Forecast_Rain = Property(0, readonly=True)
    Forecast_Snow = Property(0, readonly=True)
    # Forecast_Coverage = Property(0, readonly=True)
    # Forecast_Intensity = Property(0, readonly=True)
    # Forecast_Weather_Condition = Property(0, readonly=True)
    # Forecast_Cloud_Condition = Property(0, readonly=True)

    # unit properties
    Temperature_units = ''
    Temperature_High_units = ''
    Temperature_Low_units = ''
    Feels_Like_units = ''
    Temperature_Average_units = ''
    Humidity_units = ''
    Pressure_units = ''
    Dew_Point_units = ''
    Wind_Speed_units = ''
    Wind_Direction_units = ''
    Gust_Speed_units = ''
    Total_Rain_Today_units = ''
    Light_units = ''
    Evapotranspiration_units = ''
    Irrigation_Requirement_units = ''
    Water_Deficit_Yesterday_units = ''
    Elevation_units = ''
    # Coverage_units = ''
    # Intensity_units = ''
    # Weather_Condition_units = ''
    # Cloud_Condition_units = ''
    Average_Temperature_Tomorrow_units = ''
    High_Temperature_Tomorrow_units = ''
    Low_Temperature_Tomorrow_units = ''
    Humidity_Tomorrow_units = ''
    Wind_Speed_Tomorrow_units = ''
    Gust_Speed_Tomorrow_units = ''
    Rain_Tomorrow_units = ''
    Snow_Tomorrow_units = ''
    # Coverage_Tomorrow_units = ''
    # Intensity_Tomorrow_units = ''
    # Weather_Condition_Tomorrow_units = ''
    # Cloud_Condition_Tomorrow_units = ''
    Forecast_Average_Temperature_units = ''
    Forecast_High_Temperature_units = ''
    Forecast_Low_Temperature_units = ''
    Forecast_Humidity_units = ''
    Forecast_Rain_units = ''
    Forecast_Snow_units = ''
    # Forecast_Coverage_units = ''
    # Forecast_Intensity_units = ''
    # Forecast_Weather_Condition_units = ''
    # Forecast_Cloud_Condition_units = ''

    def __init__(self, parent, xml=None):
        super(Climate, self).__init__()
        self.parent = parent
        self.parse(xml)

    def __str__(self):
        """ Returns a string representing the climate manager. """
        return 'Climate Module'

    def __repr__(self):
        """ Returns a long string showing all the climate values. """
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
                'NNW': 337.5,
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

    def _upmsg(self, xmldoc):
        cid = int(xmldoc.getElementsByTagName('action')[0]
                  .firstChild.toxml()) - 1
        val_raw = xmldoc.getElementsByTagName('value')[0] \
            .firstChild.toxml().strip()
        unit_raw = xmldoc.getElementsByTagName('unit')[0].firstChild
        if unit_raw is not None:
            unit_raw = unit_raw.toxml().strip()
        else:
            unit_raw = ''

        if cid < len(self._id2name):
            (val, unit) = self._parse_val((val_raw + ' ' + unit_raw).strip())
            cname = self._id2name[cid]
            if cname is not None:
                attr = getattr(self, cname)
                attr.update(val, force=True, silent=True)
                setattr(self, cname + '_units', unit)

                self.parent.log.info('ISY Updated Climate Value: ' + cname)
