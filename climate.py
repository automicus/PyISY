
from xml.dom import minidom
from time import sleep
from ISYtypes import MonitoredDict
from math import atan, pi

_thread_sleeptime = 0.75

class climate(MonitoredDict):

    """
    climate class

    DESCRIPTION:
        This class handles the ISY climate module.

    USAGE:
        This object may be used in a similar way as a 
        dictionary with the parameter names being 
        used as keys.

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

    EXAMPLE:
        >>> climate['Temperature']
        79
        >>> climate.units['Temperature']
        F

    ATTRIBUTES:
        parent: The ISY device class
        units: Dictionary of each parameter's unit

    """
    
    def __init__(self, parent, xml=None):
        """
        Initiates climate class.

        parent: ISY class
        xml: String of xml data containing the climate data
        """
        super(climate, self).__init__()
        self.parent = parent
        self.units = {}

        self.parse(xml)

    def parse(self, xml):
        """
        Parses the xml data.

        xml: String of the xml data
        """
        try:
            xmldoc = minidom.parseString(xml)
        except:
            self.parent.log.error('ISY Could not parse climate, poorly formatted XML.')
        else:
            # parse definitions
            feature = xmldoc.getElementsByTagName('climate')[0]

            for node in feature.childNodes:
                (val, unit) = self._parse_val(node.firstChild.toxml())
                name = node.nodeName
                self[name] = val
                self.units[name] = unit

            self.parent.log.info('ISY Loaded Environment Data')

    def _parse_val(self, val):
        try:
            # assume standard val unit combination
            split_val = val.split()
            if len(split_val) == 2:
                return (float(split_val[0]), split_val[1])
            else:
                # probably elevation, assume feet
                return (float(split_val[0]), 'feet')
        except ValueError:
            # assume direction
            # calculate direction vector
            vector = [0., 0.]
            for direction in val:
                if direction == 'N':
                    vector[0] += 1.
                elif direction == 'E':
                    vector[1] += 1.
                elif direction == 'S':
                    vector[0] -= 1.
                elif direction == 'W':
                    vector[1] -= 1.
            # convert to unit vector
            mag = sum([v**2 for v in vector])**(0.5)
            unit_vector = [v/mag for v in vector]
            # convert unit vector to angle
            try:
                angle = atan(vector[1]/vector[0]) * 180./pi
            except ZeroDivisionError:
                angle = 0 if vector[0]>=0 else 1
            return (angle, 'deg')
            
    def update(self, waitTime=0):
        """
        Updates the contents of the climate class

        waitTime: [optional] Amount of seconds to wait before updating
        """
        time.sleep(waitTime)
        xml = self.parent.conn.getClimate()
        self.parse(xml)

    def updateThread(self):
        """
        Continually updates the class until it is told to stop.
        Should be run in a thread.
        """
        while self.parent.auto_update:
            self.update(_thread_sleeptime) 