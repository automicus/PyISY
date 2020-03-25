"""Constants for the PyISY Module."""
import datetime

UPDATE_INTERVAL = 0.5

# Time Constants / Strings
EMPTY_TIME = datetime.datetime(year=1, month=1, day=1)
ISY_EPOCH_OFFSET = 36524
MILITARY_TIME = "%Y/%m/%d %H:%M:%S"
STANDARD_TIME = "%Y/%m/%d %I:%M:%S %p"
XML_STRPTIME = "%Y%m%d %H:%M:%S"
XML_STRPTIME_YY = "%y%m%d %H:%M:%S"
XML_TRUE = "true"
XML_FALSE = "false"
XML_ON = "<on />"
XML_OFF = "<off />"

POLL_TIME = 5
SOCKET_BUFFER_SIZE = 4096
THREAD_SLEEP_TIME = 30.0

ISY_VALUE_UNKNOWN = -1 * float("inf")

XML_PARSE_ERROR = "ISY Could not parse response, poorly formatted XML."

""" Dictionary of X10 commands. """
X10_COMMANDS = {"all_off": 1, "all_on": 4, "on": 3, "off": 11, "bright": 7, "dim": 15}

CARDINAL_DIRECTIONS = {
    "N": 0.0,
    "NNE": 22.5,
    "NE": 45.0,
    "ENE": 67.5,
    "E": 90.0,
    "ESE": 112.5,
    "SE": 135.0,
    "SSE": 157.5,
    "S": 180.0,
    "SSW": 202.5,
    "SW": 225.0,
    "WSW": 247.5,
    "W": 270.0,
    "WNW": 292.5,
    "NW": 315.0,
    "NNW": 337.5,
    "N/A": None,
}

ATTR_ACTION = "action"
ATTR_CONTROL = "control"
ATTR_DESC = "desc"
ATTR_FLAG = "flag"
ATTR_FORMATTED = "formatted"
ATTR_ID = "id"
ATTR_INIT = "init"
ATTR_INSTANCE = "instance"
ATTR_NODE_DEF_ID = "nodeDefId"
ATTR_PARENT = "parentId"
ATTR_PRECISION = "prec"
ATTR_SET = "set"
ATTR_STATUS = "status"
ATTR_STREAM_ID = "sid"
ATTR_TS = "ts"
ATTR_UNIT_OF_MEASURE = "uom"
ATTR_VAL = "val"  # Used for Variables.
ATTR_VALUE = "value"  # Used for everything else.
ATTR_VAR = "var"

TAG_ADDRESS = "address"
TAG_CATEGORY = "cat"
TAG_DESC = "desc"
TAG_DEVICE_TYPE = "devtype"
TAG_DST = "DST"
TAG_ENABLED = "enabled"
TAG_FAMILY = "family"
TAG_FEATURE = "feature"
TAG_FIRMWARE = "app_full_version"
TAG_FOLDER = "folder"
TAG_FORMATTED = "fmtAct"
TAG_GROUP = "group"
TAG_INSTALLED = "isInstalled"
TAG_LATITUDE = "Lat"
TAG_LINK = "link"
TAG_LONGITUDE = "Long"
TAG_MILIATRY_TIME = "IsMilitary"
TAG_NAME = "name"
TAG_NET_RULE = "NetRule"
TAG_NODE = "node"
TAG_NODE_DEFS = "nodedefs"
TAG_NTP = "NTP"
TAG_PARENT = "parent"
TAG_PRGM_FINISH = "f"
TAG_PRGM_RUN = "r"
TAG_PRGM_RUNNING = "running"
TAG_PRGM_STATUS = "s"
TAG_PRIMARY_NODE = "pnode"
TAG_PRODUCT = "product"
TAG_PROGRAM = "program"
TAG_PROPERTY = "property"
TAG_ROOT = "root"
TAG_SPOKEN = "spoken"
TAG_SUNRISE = "Sunrise"
TAG_SUNSET = "Sunset"
TAG_TYPE = "type"
TAG_TZ_OFFSET = "TMZOffset"
TAG_VARIABLE = "e"
TAG_VARIABLES = "variables"

PROTO_FOLDER = "program_folder"
PROTO_GROUP = "group"
PROTO_INSTEON = "insteon"
PROTO_INT_VAR = "integer_variable"
PROTO_NODE_SERVER = "node_server"
PROTO_PROGRAM = "program"
PROTO_STATE_VAR = "state_variable"
PROTO_ZIGBEE = "zigbee"
PROTO_ZWAVE = "zwave"

PROP_BATTERY_LEVEL = "BATLVL"
PROP_BUSY = "BUSY"
PROP_ENERGY_MODE = "CLIEMD"
PROP_HEAT_COOL_STATE = "CLIHCS"
PROP_HUMIDITY = "CLIHUM"
PROP_ON_LEVEL = "OL"
PROP_RAMP_RATE = "RR"
PROP_SCHEDULE_MODE = "CLISMD"
PROP_SETPOINT_COOL = "CLISPC"
PROP_SETPOINT_HEAT = "CLISPH"
PROP_STATUS = "ST"
PROP_TEMPERATURE = "CLITEMP"
PROP_UOM = "UOM"

METHOD_GET = "get"
METHOD_COMMAND = "cmd"

UOM_SECONDS = "57"

URL_CLIMATE = "climate"
URL_CLOCK = "time"
URL_CONFIG = "config"
URL_DEFINITIONS = "definitions"
URL_MEMBERS = "members"
URL_NETWORK = "networking"
URL_NODES = "nodes"
URL_NOTES = "notes"
URL_PING = "ping"
URL_PROGRAMS = "programs"
URL_RESOURCES = "resources"
URL_STATUS = "status"
URL_SUBFOLDERS = "subfolders"
URL_VARIABLES = "vars"

VAR_INTEGER = "1"
VAR_STATE = "2"

CLIMATE_SETPOINT_MIN_GAP = 2

CMD_BEEP = "BEEP"
CMD_BRIGHTEN = "BRT"
CMD_CLIMATE_FAN_SPEED = "CLIFS"
CMD_CLIMATE_MODE = "CLIMD"
CMD_DIM = "DIM"
CMD_DISABLE = "disable"
CMD_DISABLE_RUN_AT_STARTUP = "disableRunAtStartup"
CMD_ENABLE = "enable"
CMD_ENABLE_RUN_AT_STARTUP = "enableRunAtStartup"
CMD_FADE_DOWN = "FDDOWN"
CMD_FADE_STOP = "FDSTOP"
CMD_FADE_UP = "FDUP"
CMD_MANUAL_DIM_BEGIN = "BMAN"
CMD_MANUAL_DIM_STOP = "SMAN"
CMD_OFF = "DOF"
CMD_OFF_FAST = "DFOF"
CMD_ON = "DON"
CMD_ON_FAST = "DFON"
CMD_RESET = "RESET"
CMD_RUN = "run"
CMD_RUN_ELSE = "runElse"
CMD_RUN_THEN = "runThen"
CMD_SECURE = "SECMD"
CMD_STOP = "stop"
CMD_X10 = "X10"

COMMAND_FRIENDLY_NAME = {
    "AIRFLOW": "air_flow",
    "ALARM": "alarm",
    "ANGLE": "angle_position",
    "ATMPRES": "atmospheric_pressure",
    "BARPRES": "barometric_pressure",
    "CC": "current",
    "CO2LVL": "co2_level",
    "CPW": "power",
    "CV": "voltage",
    "DISTANC": "distance",
    "ELECCON": "electrical_conductivity",
    "ELECRES": "electrical_resistivity",
    "ERR": "device_communication_errors",
    "GPV": "general_purpose",
    "GVOL": "gas_volume",
    "LUMIN": "luminance",
    "MOIST": "moisture",
    "PCNT": "pulse_count",
    "PF": "power_factor",
    "PPW": "polarized_power",
    "PULSCNT": "pulse_count",
    "RAINRT": "rain_rate",
    "ROTATE": "rotation",
    "RR": "ramp_rate",
    "SEISINT": "seismic_intensity",
    "SEISMAG": "seismic_magnitude",
    "SOLRAD": "solar_radiation",
    "SPEED": "speed",
    "SVOL": "sound_volume",
    "TANKCAP": "tank_capacity",
    "TIDELVL": "tide_level",
    "TIMEREM": "time_remaining",
    "TPW": "total_kw_power",
    "UAC": "user_number",
    "USRNUM": "user_number",
    "UV": "uv_light",
    "VOCLVL": "voc_level",
    "WEIGHT": "weight",
    "WINDDIR": "wind_direction",
    "WVOL": "water_volume",
    CMD_BEEP: "beep",
    CMD_BRIGHTEN: "bright",
    CMD_CLIMATE_FAN_SPEED: "fan_state",
    CMD_CLIMATE_MODE: "climate_mode",
    CMD_DIM: "dim",
    CMD_FADE_DOWN: "fade_down",
    CMD_FADE_STOP: "fade_stop",
    CMD_FADE_UP: "fade_up",
    CMD_MANUAL_DIM_BEGIN: "brighten_manual",
    CMD_MANUAL_DIM_STOP: "stop_manual",
    CMD_OFF: "off",
    CMD_OFF_FAST: "fastoff",
    CMD_ON: "on",
    CMD_ON_FAST: "faston",
    CMD_RESET: "reset",
    CMD_SECURE: "secure",
    CMD_X10: "x10_command",
    PROP_BATTERY_LEVEL: "battery_level",
    PROP_BUSY: "busy",
    PROP_ENERGY_MODE: "energy_saving_mode",
    PROP_HEAT_COOL_STATE: "heat_cool_state",
    PROP_HUMIDITY: "humidity",
    PROP_ON_LEVEL: "on_level",
    PROP_SCHEDULE_MODE: "schedule_mode",
    PROP_SETPOINT_COOL: "cool_setpoint",
    PROP_SETPOINT_HEAT: "heat_setpoint",
    PROP_STATUS: "status",
    PROP_TEMPERATURE: "temperature",
    PROP_UOM: "unit_of_measure",
}

EVENT_PROPS_IGNORED = [
    CMD_BEEP,
    CMD_BRIGHTEN,
    CMD_DIM,
    CMD_MANUAL_DIM_BEGIN,
    CMD_MANUAL_DIM_STOP,
    CMD_FADE_UP,
    CMD_FADE_DOWN,
    CMD_FADE_STOP,
    CMD_OFF,
    CMD_OFF_FAST,
    CMD_ON,
    CMD_ON_FAST,
    CMD_RESET,
    CMD_X10,
    PROP_BUSY,
    PROP_STATUS,
]

COMMAND_NAME = {val: key for key, val in COMMAND_FRIENDLY_NAME.items()}

# Referenced from ISY-WSDK-5.0.4\WSDL\family.xsd
NODE_FAMILY_ID = {
    "0": "Default",
    "1": "Insteon",
    "2": "UPB",
    "3": "RCS",
    "4": "ZWave",
    "5": "Auto DR",
    "6": "Group",
    "7": "UDI",
    "8": "Brultech",
    "9": "NCD",
    "10": "Node Server",
}

UOM_SECONDS = "57"
UOM_FAN_SPEEDS = "99"
UOM_CLIMATE_MODES = "98"

UOM_FRIENDLY_NAME = {
    "1": "A",
    "3": "btu/h",
    "4": "°C",
    "5": "cm",
    "6": "ft³",
    "7": "ft³/min",
    "8": "m³",
    "9": "day",
    "10": "days",
    "12": "dB",
    "13": "dB A",
    "14": "°",
    "16": "macroseismic",
    "17": "°F",
    "18": "ft",
    "19": "hour",
    "20": "hours",
    "21": "%AH",
    "22": "%RH",
    "23": "inHg",
    "24": "in/hr",
    "25": "index",
    "26": "K",
    "27": "keyword",
    "28": "kg",
    "29": "kV",
    "30": "kW",
    "31": "kPa",
    "32": "KPH",
    "33": "kWh",
    "34": "liedu",
    "35": "L",
    "36": "lx",
    "37": "mercalli",
    "38": "m",
    "39": "m³/hr",
    "40": "m/s",
    "41": "mA",
    "42": "ms",
    "43": "mV",
    "44": "min",
    "45": "min",
    "46": "mm/hr",
    "47": "month",
    "48": "MPH",
    "49": "m/s",
    "50": "Ω",
    "51": "%",
    "52": "lbs",
    "53": "pf",
    "54": "ppm",
    "55": "pulse count",
    "57": "s",
    "58": "s",
    "59": "S/m",
    "60": "m_b",
    "61": "M_L",
    "62": "M_w",
    "63": "M_S",
    "64": "shindo",
    "65": "SML",
    "69": "gal",
    "71": "UV index",
    "72": "V",
    "73": "W",
    "74": "W/m²",
    "75": "weekday",
    "76": "°",
    "77": "year",
    "82": "mm",
    "83": "km",
    "85": "Ω",
    "86": "kΩ",
    "87": "m³/m³",
    "88": "Water activity",
    "89": "RPM",
    "90": "Hz",
    "91": "°",
    "92": "° South",
    "102": "kWs",
    "103": "$",
    "104": "¢",
    "105": "in",
    "106": "mm/day",
}

UOM_TO_STATES = {
    "11": {  # Deadbolt Status
        "0": "unlocked",
        "100": "locked",
        "101": "unknown",
        "102": "problem",
    },
    "15": {  # Door Lock Alarm
        "1": "master code changed",
        "2": "tamper code entry limit",
        "3": "escutcheon removed",
        "4": "manually locked",
        "5": "locked by touch",
        "6": "manually unlocked",
        "7": "remote locking jammed bolt",
        "8": "remotely locked",
        "9": "remotely unlocked",
        "10": "deadbolt jammed",
        "11": "battery too low to operate",
        "12": "critical low battery",
        "13": "low battery",
        "14": "automatically locked",
        "15": "automatic locking jammed bolt",
        "16": "remotely power cycled",
        "17": "lock handling complete",
        "19": "user deleted",
        "20": "user added",
        "21": "duplicate pin",
        "22": "jammed bolt by locking with keypad",
        "23": "locked by keypad",
        "24": "unlocked by keypad",
        "25": "keypad attempt outside schedule",
        "26": "hardware failure",
        "27": "factory reset",
    },
    "66": {  # Thermostat Heat/Cool State
        "0": "idle",
        "1": "heating",
        "2": "cooling",
        "3": "fan_only",
        "4": "pending heat",
        "5": "pending cool",
        "6": "vent",
        "7": "aux heat",
        "8": "2nd stage heating",
        "9": "2nd stage cooling",
        "10": "2nd stage aux heat",
        "11": "3rd stage aux heat",
    },
    "67": {  # Thermostat Mode
        "0": "off",
        "1": "heat",
        "2": "cool",
        "3": "auto",
        "4": "aux/emergency heat",
        "5": "resume",
        "6": "fan_only",
        "7": "furnace",
        "8": "dry air",
        "9": "moist air",
        "10": "auto changeover",
        "11": "energy save heat",
        "12": "energy save cool",
        "13": "away",
    },
    "68": {  # Thermostat Fan Mode
        "0": "auto",
        "1": "on",
        "2": "auto high",
        "3": "high",
        "4": "auto medium",
        "5": "medium",
        "6": "circulation",
        "7": "humidity circulation",
    },
    "78": {"0": "off", "100": "on"},  # 0-Off 100-On
    "79": {"0": "open", "100": "closed"},  # 0-Open 100-Close
    "80": {  # Thermostat Fan Run State
        "0": "off",
        "1": "on",
        "2": "on high",
        "3": "on medium",
        "4": "circulation",
        "5": "humidity circulation",
        "6": "right/left circulation",
        "7": "up/down circulation",
        "8": "quiet circulation",
    },
    "84": {"0": "unlock", "1": "lock"},  # Secure Mode
    "93": {  # Power Management Alarm
        "1": "power applied",
        "2": "ac mains disconnected",
        "3": "ac mains reconnected",
        "4": "surge detection",
        "5": "volt drop or drift",
        "6": "over current detected",
        "7": "over voltage detected",
        "8": "over load detected",
        "9": "load error",
        "10": "replace battery soon",
        "11": "replace battery now",
        "12": "battery is charging",
        "13": "battery is fully charged",
        "14": "charge battery soon",
        "15": "charge battery now",
    },
    "94": {  # Appliance Alarm
        "1": "program started",
        "2": "program in progress",
        "3": "program completed",
        "4": "replace main filter",
        "5": "failure to set target temperature",
        "6": "supplying water",
        "7": "water supply failure",
        "8": "boiling",
        "9": "boiling failure",
        "10": "washing",
        "11": "washing failure",
        "12": "rinsing",
        "13": "rinsing failure",
        "14": "draining",
        "15": "draining failure",
        "16": "spinning",
        "17": "spinning failure",
        "18": "drying",
        "19": "drying failure",
        "20": "fan failure",
        "21": "compressor failure",
    },
    "95": {  # Home Health Alarm
        "1": "leaving bed",
        "2": "sitting on bed",
        "3": "lying on bed",
        "4": "posture changed",
        "5": "sitting on edge of bed",
    },
    "96": {  # VOC Level
        "1": "clean",
        "2": "slightly polluted",
        "3": "moderately polluted",
        "4": "highly polluted",
    },
    "97": {  # Barrier Status
        **{
            "0": "closed",
            "100": "open",
            "101": "unknown",
            "102": "stopped",
            "103": "closing",
            "104": "opening",
        },
        **{
            str(b): "{} %".format(b) for a, b in enumerate(list(range(1, 100)))
        },  # 1-99 are percentage open
    },
    "98": {  # Insteon Thermostat Mode
        "0": "off",
        "1": "heat",
        "2": "cool",
        "3": "auto",
        "4": "fan_only",
        "5": "program_auto",
        "6": "program_heat",
        "7": "program_cool",
    },
    "99": {"7": "on", "8": "auto"},  # Insteon Thermostat Fan Mode
}

# Translate the "RR" Property to Seconds
INSTEON_RAMP_RATES = {
    "0": 540,
    "1": 480,
    "2": 420,
    "3": 360,
    "4": 300,
    "5": 270,
    "6": 240,
    "7": 210,
    "8": 180,
    "9": 150,
    "10": 120,
    "11": 90,
    "12": 60,
    "13": 47,
    "14": 43,
    "15": 38.5,
    "16": 34,
    "17": 32,
    "18": 30,
    "19": 28,
    "20": 26,
    "21": 23.5,
    "22": 21.5,
    "23": 19,
    "24": 8.5,
    "25": 6.5,
    "26": 4.5,
    "27": 2,
    "28": 0.5,
    "29": 0.3,
    "30": 0.2,
    "31": 0.1,
}

# Thermostat Types/Categories. 4.8 Trane, 5.3 venstar, 5.10 Insteon Wireless,
#  5.11 Insteon, 5.17 Insteon (EU), 5.18 Insteon (Aus/NZ)
THERMOSTAT_TYPES = ["4.8", "5.3", "5.10", "5.11", "5.17", "5.18"]
THERMOSTAT_ZWAVE_CAT = ["140"]
