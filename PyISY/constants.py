"""Constants for the PyISY Module."""
import datetime

UPDATE_INTERVAL = 0.5
EMPTY_TIME = datetime.datetime(year=1, month=1, day=1)

POLL_TIME = 5
THREAD_SLEEP_TIME = 30.0

VALUE_UNKNOWN = -1 * float('inf')

XML_PARSE_ERROR = 'ISY Could not parse response, poorly formatted XML.'

""" Dictionary of X10 commands. """
X10_COMMANDS = {
    'all_off': 1,
    'all_on': 4,
    'on': 3,
    'off': 11,
    'bright': 7,
    'dim': 15
}

CARDINAL_DIRECTIONS = {
    'N': 0.,
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
    'N/A': None
}

STATE_PROPERTY = 'ST'
BATLVL_PROPERTY = 'BATLVL'

ATTR_ID = 'id'
ATTR_NAME = 'name'
ATTR_INIT = 'init'
ATTR_UOM = 'uom'
ATTR_VAL = 'val'        # Used for Variables.
ATTR_VALUE = 'value'    # Used for everything else.
ATTR_VAR = 'var'
ATTR_VARS = 'vars'
ATTR_SET = 'set'
ATTR_GET = 'get'
ATTR_PREC = 'prec'
ATTR_FORMATTED = 'formatted'
ATTR_NODE = 'node'
ATTR_GROUP = 'group'
ATTR_FOLDER = 'folder'
ATTR_ACTION = 'action'
ATTR_TYPE = 'type'
ATTR_TS = 'ts'
ATTR_DESC = 'desc'
ATTR_FLAG = 'flag'
ATTR_CONTROL = 'control'

VAR_INTEGER = '1'
VAR_STATE = '2'


CLIMATE_SETPOINT_MIN_GAP = 2

COMMAND_FRIENDLY_NAME = {
    'OL': 'on_level',
    'RR': 'ramp_rate',
    'CLISPH': 'heat_setpoint',
    'CLISPC': 'cool_setpoint',
    'CLIFS': 'fan_state',
    'CLIHUM': 'humidity',
    'CLIHCS': 'heat_cool_state',
    'CLIEMD': 'energy_saving_mode',
    'ERR': 'device_communication_errors',
    'UOM': 'unit_of_measure',
    'TPW': 'total_kw_power',
    'PPW': 'polarized_power',
    'PF': 'power_factor',
    'CC': 'current',
    'CV': 'voltage',
    'AIRFLOW': 'air_flow',
    'ALARM': 'alarm',
    'ANGLE': 'angle_position',
    'ATMPRES': 'atmospheric_pressure',
    'BARPRES': 'barometric_pressure',
    'BATLVL': 'battery_level',
    'CLIMD': 'climate_mode',
    'CLISMD': 'schedule_mode',
    'CLITEMP': 'temperature',
    'CO2LVL': 'co2_level',
    'CPW': 'power',
    'DISTANC': 'distance',
    'ELECRES': 'electrical_resistivity',
    'ELECCON': 'electrical_conductivity',
    'GPV': 'general_purpose',
    'GVOL': 'gas_volume',
    'LUMIN': 'luminance',
    'MOIST': 'moisture',
    'PCNT': 'pulse_count',
    'PULSCNT': 'pulse_count',
    'RAINRT': 'rain_rate',
    'ROTATE': 'rotation',
    'SEISINT': 'seismic_intensity',
    'SEISMAG': 'seismic_magnitude',
    'SOLRAD': 'solar_radiation',
    'SPEED': 'speed',
    'SVOL': 'sound_volume',
    'TANKCAP': 'tank_capacity',
    'TIDELVL': 'tide_level',
    'TIMEREM': 'time_remaining',
    'UAC': 'user_number',
    'UV': 'uv_light',
    'USRNUM': 'user_number',
    'VOCLVL': 'voc_level',
    'WEIGHT': 'weight',
    'WINDDIR': 'wind_direction',
    'WVOL': 'water_volume',
    'DON': 'on',
    'ST': 'status',
    'DFON': 'faston',
    'DOF': 'off',
    'DFOF': 'fastoff',
    'BEEP': 'beep',
    'RESET': 'reset',
    'X10': 'x10_command',
    'BMAN': 'brighten_manual',
    'SMAN': 'stop_manual',
    'BRT': 'bright',
    'DIM': 'dim',
    'BUSY': 'busy',
    'SECMD': 'secure'
}

COMMAND_NAME = {val: key for key, val in COMMAND_FRIENDLY_NAME.items()}

UOM_FRIENDLY_NAME = {
    '1': 'A',
    '3': 'btu/h',
    '4': '°C',
    '5': 'cm',
    '6': 'ft³',
    '7': 'ft³/min',
    '8': 'm³',
    '9': 'day',
    '10': 'days',
    '12': 'dB',
    '13': 'dB A',
    '14': '°',
    '16': 'macroseismic',
    '17': '°F',
    '18': 'ft',
    '19': 'hour',
    '20': 'hours',
    '21': '%AH',
    '22': '%RH',
    '23': 'inHg',
    '24': 'in/hr',
    '25': 'index',
    '26': 'K',
    '27': 'keyword',
    '28': 'kg',
    '29': 'kV',
    '30': 'kW',
    '31': 'kPa',
    '32': 'KPH',
    '33': 'kWh',
    '34': 'liedu',
    '35': 'L',
    '36': 'lx',
    '37': 'mercalli',
    '38': 'm',
    '39': 'm³/hr',
    '40': 'm/s',
    '41': 'mA',
    '42': 'ms',
    '43': 'mV',
    '44': 'min',
    '45': 'min',
    '46': 'mm/hr',
    '47': 'month',
    '48': 'MPH',
    '49': 'm/s',
    '50': 'Ω',
    '51': '%',
    '52': 'lbs',
    '53': 'pf',
    '54': 'ppm',
    '55': 'pulse count',
    '57': 's',
    '58': 's',
    '59': 'S/m',
    '60': 'm_b',
    '61': 'M_L',
    '62': 'M_w',
    '63': 'M_S',
    '64': 'shindo',
    '65': 'SML',
    '69': 'gal',
    '71': 'UV index',
    '72': 'V',
    '73': 'W',
    '74': 'W/m²',
    '75': 'weekday',
    '76': '°',
    '77': 'year',
    '82': 'mm',
    '83': 'km',
    '85': 'Ω',
    '86': 'kΩ',
    '87': 'm³/m³',
    '88': 'Water activity',
    '89': 'RPM',
    '90': 'Hz',
    '91': '°',
    '92': '° South',
    '102': 'kWs',
    '103': '$',
    '104': '¢',
    '105': 'in',
    '106': 'mm/day'
}

UOM_TO_STATES = {
    '11': {  # Deadbolt Status
        '0': 'unlocked',
        '100': 'locked',
        '101': 'unknown',
        '102': 'problem',
    },
    '15': {  # Door Lock Alarm
        '1': 'master code changed',
        '2': 'tamper code entry limit',
        '3': 'escutcheon removed',
        '4': 'manually locked',
        '5': 'locked by touch',
        '6': 'manually unlocked',
        '7': 'remote locking jammed bolt',
        '8': 'remotely locked',
        '9': 'remotely unlocked',
        '10': 'deadbolt jammed',
        '11': 'battery too low to operate',
        '12': 'critical low battery',
        '13': 'low battery',
        '14': 'automatically locked',
        '15': 'automatic locking jammed bolt',
        '16': 'remotely power cycled',
        '17': 'lock handling complete',
        '19': 'user deleted',
        '20': 'user added',
        '21': 'duplicate pin',
        '22': 'jammed bolt by locking with keypad',
        '23': 'locked by keypad',
        '24': 'unlocked by keypad',
        '25': 'keypad attempt outside schedule',
        '26': 'hardware failure',
        '27': 'factory reset'
    },
    '66': {  # Thermostat Heat/Cool State
        '0': 'idle',
        '1': 'heating',
        '2': 'cooling',
        '3': 'fan_only',
        '4': 'pending heat',
        '5': 'pending cool',
        '6': 'vent',
        '7': 'aux heat',
        '8': '2nd stage heating',
        '9': '2nd stage cooling',
        '10': '2nd stage aux heat',
        '11': '3rd stage aux heat'
    },
    '67': {  # Thermostat Mode
        '0': 'off',
        '1': 'heat',
        '2': 'cool',
        '3': 'auto',
        '4': 'aux/emergency heat',
        '5': 'resume',
        '6': 'fan_only',
        '7': 'furnace',
        '8': 'dry air',
        '9': 'moist air',
        '10': 'auto changeover',
        '11': 'energy save heat',
        '12': 'energy save cool',
        '13': 'away'
    },
    '68': {  # Thermostat Fan Mode
        '0': 'auto',
        '1': 'on',
        '2': 'auto high',
        '3': 'high',
        '4': 'auto medium',
        '5': 'medium',
        '6': 'circulation',
        '7': 'humidity circulation'
    },
    '78': {  # 0-Off 100-On
        '0': 'off',
        '100': 'on'
    },
    '79': {  # 0-Open 100-Close
        '0': 'open',
        '100': 'closed'
    },
    '80': {  # Thermostat Fan Run State
        '0': 'off',
        '1': 'on',
        '2': 'on high',
        '3': 'on medium',
        '4': 'circulation',
        '5': 'humidity circulation',
        '6': 'right/left circulation',
        '7': 'up/down circulation',
        '8': 'quiet circulation'
    },
    '84': {  # Secure Mode
        '0': 'unlock',
        '1': 'lock'
    },
    '93': {  # Power Management Alarm
        '1': 'power applied',
        '2': 'ac mains disconnected',
        '3': 'ac mains reconnected',
        '4': 'surge detection',
        '5': 'volt drop or drift',
        '6': 'over current detected',
        '7': 'over voltage detected',
        '8': 'over load detected',
        '9': 'load error',
        '10': 'replace battery soon',
        '11': 'replace battery now',
        '12': 'battery is charging',
        '13': 'battery is fully charged',
        '14': 'charge battery soon',
        '15': 'charge battery now'
    },
    '94': {  # Appliance Alarm
        '1': 'program started',
        '2': 'program in progress',
        '3': 'program completed',
        '4': 'replace main filter',
        '5': 'failure to set target temperature',
        '6': 'supplying water',
        '7': 'water supply failure',
        '8': 'boiling',
        '9': 'boiling failure',
        '10': 'washing',
        '11': 'washing failure',
        '12': 'rinsing',
        '13': 'rinsing failure',
        '14': 'draining',
        '15': 'draining failure',
        '16': 'spinning',
        '17': 'spinning failure',
        '18': 'drying',
        '19': 'drying failure',
        '20': 'fan failure',
        '21': 'compressor failure'
    },
    '95': {  # Home Health Alarm
        '1': 'leaving bed',
        '2': 'sitting on bed',
        '3': 'lying on bed',
        '4': 'posture changed',
        '5': 'sitting on edge of bed'
    },
    '96': {  # VOC Level
        '1': 'clean',
        '2': 'slightly polluted',
        '3': 'moderately polluted',
        '4': 'highly polluted'
    },
    '97': {  # Barrier Status
        **{
            '0': 'closed',
            '100': 'open',
            '101': 'unknown',
            '102': 'stopped',
            '103': 'closing',
            '104': 'opening'
            },
        **{str(b): '{} %'.format(b) for a, b in \
           enumerate(list(range(1, 100)))}  # 1-99 are percentage open
    },
    '98': {  # Insteon Thermostat Mode
        '0': 'off',
        '1': 'heat',
        '2': 'cool',
        '3': 'auto',
        '4': 'fan_only',
        '5': 'program_auto',
        '6': 'program_heat',
        '7': 'program_cool'
    },
    '99': {  # Insteon Thermostat Fan Mode
        '7': 'on',
        '8': 'auto'
    }
}
