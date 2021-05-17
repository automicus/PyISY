"""Constants for the PyISY Module."""
import datetime
import logging

_LOGGER = logging.getLogger(__package__)
LOG_LEVEL = logging.DEBUG
LOG_VERBOSE = 5
LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

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

POLL_TIME = 10
RECONNECT_DELAY = 60
SOCKET_BUFFER_SIZE = 4096
THREAD_SLEEP_TIME = 30.0

ES_LOST_STREAM_CONNECTION = "lost_stream_connection"
ES_CONNECTED = "connected"
ES_DISCONNECTED = "disconnected"
ES_START_UPDATES = "start_updates"
ES_STOP_UPDATES = "stop_updates"
ES_INITIALIZING = "stream_initializing"
ES_LOADED = "stream_loaded"
ES_RECONNECT_FAILED = "reconnect_failed"
ES_RECONNECTING = "reconnecting"
ES_DISCONNECTING = "stream_disconnecting"
ES_NOT_STARTED = "not_started"

ISY_VALUE_UNKNOWN = -1 * float("inf")
ISY_PROP_NOT_SET = "-1"

""" Dictionary of X10 commands. """
X10_COMMANDS = {"all_off": 1, "all_on": 4, "on": 3, "off": 11, "bright": 7, "dim": 15}

ACTION_EVENT_STATUS = "0"
ACTION_GET_STATUS = "1"
ACTION_KEY_CHANGED = "2"
ACTION_INFO_STRING = "3"
ACTION_IR_LEARN = "4"
ACTION_SCHEDULE = "5"
ACTION_VAR_STATUS = "6"
ACTION_VAR_INIT = "7"
ACTION_KEY = "8"

ATTR_ACTION = "action"
ATTR_CONTROL = "control"
ATTR_DESC = "desc"
ATTR_FLAG = "flag"
ATTR_FORMATTED = "formatted"
ATTR_ID = "id"
ATTR_INIT = "init"
ATTR_INSTANCE = "instance"
ATTR_LAST_CHANGED = "last_changed"
ATTR_LAST_UPDATE = "last_update"
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

DEFAULT_PRECISION = "0"
DEFAULT_UNIT_OF_MEASURE = ""

TAG_ADDRESS = "address"
TAG_CATEGORY = "cat"
TAG_CONFIG = "config"
TAG_DESC = "desc"
TAG_DESCRIPTION = "description"
TAG_DEVICE_TYPE = "devtype"
TAG_DST = "DST"
TAG_ENABLED = "enabled"
TAG_EVENT_INFO = "eventInfo"
TAG_FAMILY = "family"
TAG_FEATURE = "feature"
TAG_FIRMWARE = "app_full_version"
TAG_FOLDER = "folder"
TAG_FORMATTED = "fmtAct"
TAG_GENERIC = "gen"
TAG_GROUP = "group"
TAG_INSTALLED = "isInstalled"
TAG_IS_LOAD = "isLoad"
TAG_LATITUDE = "Lat"
TAG_LINK = "link"
TAG_LOCATION = "location"
TAG_LONGITUDE = "Long"
TAG_MFG = "mfg"
TAG_MILIATRY_TIME = "IsMilitary"
TAG_NAME = "name"
TAG_NET_RULE = "NetRule"
TAG_NODE = "node"
TAG_NODE_DEFS = "nodedefs"
TAG_NTP = "NTP"
TAG_PARENT = "parent"
TAG_PARAMETER = "parameter"
TAG_PRGM_FINISH = "f"
TAG_PRGM_RUN = "r"
TAG_PRGM_RUNNING = "running"
TAG_PRGM_STATUS = "s"
TAG_PRIMARY_NODE = "pnode"
TAG_PRODUCT = "product"
TAG_PROGRAM = "program"
TAG_PROPERTY = "property"
TAG_ROOT = "root"
TAG_SIZE = "size"
TAG_SPOKEN = "spoken"
TAG_SUNRISE = "Sunrise"
TAG_SUNSET = "Sunset"
TAG_TYPE = "type"
TAG_TZ_OFFSET = "TMZOffset"
TAG_VALUE = "value"
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

FAMILY_CORE = "0"
FAMILY_INSTEON = "1"
FAMILY_UPB = "2"
FAMILY_RCS = "3"
FAMILY_ZWAVE = "4"
FAMILY_AUTO = "5"
FAMILY_GENERIC = "6"
FAMILY_UDI = "7"
FAMILY_BRULTECH = "8"
FAMILY_NCD = "9"
FAMILY_NODESERVER = "10"

PROP_BATTERY_LEVEL = "BATLVL"
PROP_BUSY = "BUSY"
PROP_COMMS_ERROR = "ERR"
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
PROP_ZWAVE_PREFIX = "ZW_"

METHOD_COMMAND = "cmd"
METHOD_GET = "get"
METHOD_SET = "set"

URL_CHANGE = "change"
URL_CLOCK = "time"
URL_CONFIG = "config"
URL_DEFINITIONS = "definitions"
URL_MEMBERS = "members"
URL_NETWORK = "networking"
URL_NODE = "node"
URL_NODES = "nodes"
URL_NOTES = "notes"
URL_PING = "ping"
URL_PROGRAMS = "programs"
URL_QUERY = "query"
URL_RESOURCES = "resources"
URL_STATUS = "status"
URL_SUBFOLDERS = "subfolders"
URL_VARIABLES = "vars"
URL_ZWAVE = "zwave"

VAR_INTEGER = "1"
VAR_STATE = "2"

CLIMATE_SETPOINT_MIN_GAP = 2

CMD_BEEP = "BEEP"
CMD_BRIGHTEN = "BRT"
CMD_CLIMATE_FAN_SETTING = "CLIFS"
CMD_CLIMATE_MODE = "CLIMD"
CMD_DIM = "DIM"
CMD_DISABLE = "disable"
CMD_DISABLE_RUN_AT_STARTUP = "disableRunAtStartup"
CMD_ENABLE = "enable"
CMD_ENABLE_RUN_AT_STARTUP = "enableRunAtStartup"
CMD_FADE_DOWN = "FDDOWN"
CMD_FADE_STOP = "FDSTOP"
CMD_FADE_UP = "FDUP"
CMD_MANUAL_DIM_BEGIN = "BMAN"  # Depreciated, use Fade
CMD_MANUAL_DIM_STOP = "SMAN"  # Depreciated, use Fade
CMD_MODE = "MODE"
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
    "ADRPST": "auto_dr_processing_state",
    "AIRFLOW": "air_flow",
    "ALARM": "alarm",
    "ANGLE": "angle_position",
    "ANGLPOS": "angle_position",
    "ATMPRES": "atmospheric_pressure",
    "AWAKE": "awake",
    "BARPRES": "barometric_pressure",
    "CC": "current",
    "CLIFRS": "fan_running_state",
    "CLIFSO": "fan_setting_override",
    "CO2LVL": "co2_level",
    "CPW": "power",
    "CTL": "controller_action",
    "CV": "voltage",
    "DELAY": "delay",
    "DEWPT": "dew_point",
    "DISTANC": "distance",
    "DOF3": "off_3x_key_presses",
    "DOF4": "off_4x_key_presses",
    "DOF5": "off_5x_key_presses",
    "DON3": "on_3x_key_presses",
    "DON4": "on_4x_key_presses",
    "DON5": "on_5x_key_presses",
    "ELECCON": "electrical_conductivity",
    "ELECRES": "electrical_resistivity",
    PROP_COMMS_ERROR: "device_communication_errors",
    "GPV": "general_purpose",
    "GV0": "custom_control_0",
    "GV1": "custom_control_1",
    "GV10": "custom_control_10",
    "GV11": "custom_control_11",
    "GV12": "custom_control_12",
    "GV13": "custom_control_13",
    "GV14": "custom_control_14",
    "GV15": "custom_control_15",
    "GV16": "custom_control_16",
    "GV17": "custom_control_17",
    "GV18": "custom_control_18",
    "GV19": "custom_control_19",
    "GV2": "custom_control_2",
    "GV20": "custom_control_20",
    "GV3": "custom_control_3",
    "GV4": "custom_control_4",
    "GV5": "custom_control_5",
    "GV6": "custom_control_6",
    "GV7": "custom_control_7",
    "GV8": "custom_control_8",
    "GV9": "custom_control_9",
    "GVOL": "gas_volume",
    "HAIL": "hail",
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
    "SOILT": "soil_temperature",
    "SOLRAD": "solar_radiation",
    "SPEED": "speed",
    "SVOL": "sound_volume",
    "TANKCAP": "tank_capacity",
    "TIDELVL": "tide_level",
    "TIMEREM": "time_remaining",
    "TPW": "total_energy_used",
    "UAC": "user_number",
    "USRNUM": "user_number",
    "UV": "uv_light",
    "VOCLVL": "voc_level",
    "WATERT": "water_temperature",
    "WEIGHT": "weight",
    "WINDDIR": "wind_direction",
    "WVOL": "water_volume",
    CMD_BEEP: "beep",
    CMD_BRIGHTEN: "bright",
    CMD_CLIMATE_FAN_SETTING: "fan_state",
    CMD_CLIMATE_MODE: "climate_mode",
    CMD_DIM: "dim",
    CMD_FADE_DOWN: "fade_down",
    CMD_FADE_STOP: "fade_stop",
    CMD_FADE_UP: "fade_up",
    CMD_MANUAL_DIM_BEGIN: "brighten_manual",
    CMD_MANUAL_DIM_STOP: "stop_manual",
    CMD_MODE: "mode",
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
UOM_FAN_MODES = "99"
UOM_CLIMATE_MODES = "98"
UOM_CLIMATE_MODES_ZWAVE = "67"
UOM_DOUBLE_TEMP = "101"

UOM_FRIENDLY_NAME = {
    "1": "A",
    "2": "",  # Binary / On-Off
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
    "100": "",
    "101": "° (x2)",
    "102": "kWs",
    "103": "$",
    "104": "¢",
    "105": "in",
    "106": "mm/day",
    "107": "",  # raw 1-byte unsigned value
    "108": "",  # raw 2-byte unsigned value
    "109": "",  # raw 3-byte unsigned value
    "110": "",  # raw 4-byte unsigned value
    "111": "",  # raw 1-byte signed value
    "112": "",  # raw 2-byte signed value
    "113": "",  # raw 3-byte signed value
    "114": "",  # raw 4-byte signed value
    "116": "mi",
    "117": "mbar",
    "118": "hPa",
    "119": "Wh",
    "120": "in/day",
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
        "4": "key-manually locked",
        "5": "locked by touch",
        "6": "key-manually unlocked",
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
        "28": "manually not fully locked",
        "29": "all user codes deleted",
        "30": "new user code not added-duplicate code",
        "31": "keypad temporarily disabled",
        "32": "keypad busy",
        "33": "new program code entered",
        "34": "rf unlock with invalid user code",
        "35": "rf lock with invalid user codes",
        "36": "window-door is open",
        "37": "window-door is closed",
        "38": "window-door handle is open",
        "39": "window-door handle is closed",
        "40": "user code entered on keypad",
        "41": "power cycled",
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
        "14": "program auto",
        "15": "program heat",
        "16": "program cool",
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
        "8": "left-right circulation",
        "9": "up-down circulation",
        "10": "quiet",
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
            str(b): f"{b} %" for a, b in enumerate(list(range(1, 100)))
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
    "115": {  # Most recent On style action taken for lamp control
        "0": "on",
        "1": "off",
        "2": "fade up",
        "3": "fade down",
        "4": "fade stop",
        "5": "fast on",
        "6": "fast off",
        "7": "triple press on",
        "8": "triple press off",
        "9": "4x press on",
        "10": "4x press off",
        "11": "5x press on",
        "12": "5x press off",
    },
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
INSTEON_TYPE_THERMOSTAT = ["4.8", "5.3", "5.10", "5.11", "5.17", "5.18"]
ZWAVE_CAT_THERMOSTAT = ["140"]

# Other special categories or types
INSTEON_TYPE_LOCK = ["4.64"]
ZWAVE_CAT_LOCK = ["111"]

INSTEON_TYPE_DIMMABLE = ["1."]
INSTEON_SUBNODE_DIMMABLE = " 1"
ZWAVE_CAT_DIMMABLE = ["109", "119", "186"]

# Insteon Battery Devices - States are ignored when checking the status of a group.
INSTEON_BATTERY_TYPE = ["0.16.", "0.17.", "0.18.", "16."]
INSTEON_BATTERY_NODEDEFID = [
    "BinaryAlarm",
    "BinaryAlarm_ADV",
    "BinaryControl",
    "BinaryControl_ADV",
    "RemoteLinc2",
    "RemoteLinc2_ADV",
]

# Referenced from ISY-WSDK 4_fam.xml
# Included for user translations in external modules.
# This is the Node.zwave_props.category property.
DEVTYPE_CATEGORIES = {
    "0": "uninitialized",
    "101": "unknown",
    "102": "alarm",
    "103": "av control point",
    "104": "binary sensor",
    "105": "class a motor control",
    "106": "class b motor control",
    "107": "class c motor control",
    "108": "controller",
    "109": "dimmer switch",
    "110": "display",
    "111": "door lock",
    "112": "doorbell",
    "113": "entry control",
    "114": "gateway",
    "115": "installer tool",
    "116": "motor multiposition",
    "117": "climate sensor",
    "118": "multilevel sensor",
    "119": "multilevel switch",
    "120": "on/off power strip",
    "121": "on/off power switch",
    "122": "on/off scene switch",
    "123": "open/close valve",
    "124": "pc controller",
    "125": "remote",
    "126": "remote control",
    "127": "av remote control",
    "128": "simple remote control",
    "129": "repeater",
    "130": "residential hrv",
    "131": "satellite receiver",
    "132": "satellite receiver",
    "133": "scene controller",
    "134": "scene switch",
    "135": "security panel",
    "136": "set-top box",
    "137": "siren",
    "138": "smoke alarm",
    "139": "subsystem controller",
    "140": "thermostat",
    "141": "toggle",
    "142": "television",
    "143": "energy meter",
    "144": "pulse meter",
    "145": "water meter",
    "146": "gas meter",
    "147": "binary switch",
    "148": "binary alarm",
    "149": "aux alarm",
    "150": "co2 alarm",
    "151": "co alarm",
    "152": "freeze alarm",
    "153": "glass break alarm",
    "154": "heat alarm",
    "155": "motion sensor",
    "156": "smoke alarm",
    "157": "tamper alarm",
    "158": "tilt alarm",
    "159": "water alarm",
    "160": "door/window alarm",
    "161": "test alarm",
    "162": "low battery alarm",
    "163": "co end of life alarm",
    "164": "malfunction alarm",
    "165": "heartbeat",
    "166": "overheat alarm",
    "167": "rapid temp rise alarm",
    "168": "underheat alarm",
    "169": "leak detected alarm",
    "170": "level drop alarm",
    "171": "replace filter alarm",
    "172": "intrusion alarm",
    "173": "tamper code alarm",
    "174": "hardware failure alarm",
    "175": "software failure alarm",
    "176": "contact police alarm",
    "177": "contact fire alarm",
    "178": "contact medical alarm",
    "179": "wakeup alarm",
    "180": "timer",
    "181": "power management",
    "182": "appliance",
    "183": "home health",
    "184": "barrier",
    "185": "notification sensor",
    "186": "color switch",
    "187": "multilevel switch off on",
    "188": "multilevel switch down up",
    "189": "multilevel switch close open",
    "190": "multilevel switch ccw cw",
    "191": "multilevel switch left right",
    "192": "multilevel switch reverse forward",
    "193": "multilevel switch pull push",
    "194": "basic set",
    "195": "wall controller",
    "196": "barrier handle",
    "197": "sound switch",
}

# Referenced from ISY-WSDK cat.xml
# Included for user translations in external modules.
# This is the first part of the Node.type property (before the first ".")
NODE_CATEGORIES = {
    "0": "generic controller",
    "1": "dimming control",
    "2": "switch/relay control",
    "3": "network bridge",
    "4": "irrigation control",
    "5": "climate control",
    "6": "pool control",
    "7": "sensors/actuators",
    "8": "home entertainment",
    "9": "energy management",
    "10": "appliance control",
    "11": "plumbing",
    "12": "communications",
    "13": "computer",
    "14": "windows/shades",
    "15": "access control",
    "16": "security/health/safety",
    "17": "surveillance",
    "18": "automotive",
    "19": "pet care",
    "20": "toys",
    "21": "timers/clocks",
    "22": "holiday",
    "113": "a10/x10",
    "127": "virtual",
    "254": "unknown",
}

# Node Change Actions
NC_NODE_RENAMED = "NN"
NC_NODE_REMOVED = "NR"
NC_NODE_MOVED = "MV"
NC_NODE_REMOVE_FROM_GROUP = "RG"
NC_NODE_ENABLED = "RG"
NC_PARENT_CHANGED = "PC"
NC_GROUP_RENAMED = "GN"
NC_GROUP_REMOVED = "GR"
NC_GROUP_ADDED = "GD"
NC_FOLDER_RENAMED = "FN"
NC_FOLDER_REMOVED = "FR"
NC_FOLDER_ADDED = "FD"
NC_NODE_ERROR = "NE"
NC_CLEAR_ERROR = "CE"
NC_NET_RENAMED = "WR"
NC_NODE_REVISED = "RV"

NODE_CHANGED_ACTIONS = [
    NC_NODE_RENAMED,
    NC_NODE_REMOVED,
    NC_NODE_MOVED,
    NC_NODE_REMOVE_FROM_GROUP,
    NC_NODE_ENABLED,
    NC_PARENT_CHANGED,
    NC_GROUP_RENAMED,
    NC_GROUP_REMOVED,
    NC_GROUP_ADDED,
    NC_FOLDER_RENAMED,
    NC_FOLDER_REMOVED,
    NC_FOLDER_ADDED,
    NC_NODE_ERROR,
    NC_CLEAR_ERROR,
    NC_NET_RENAMED,
    NC_NODE_REVISED,
]
