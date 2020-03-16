## CHANGELOG

### [v2.0.0] - Version 2.0 Initial Release

#### Summary: 

V2 is a significant refactoring and cleanup of the original PyISY code, with the primary goal of (1) fixing as many bugs in one shot as possible and (2) moving towards PEP8 compliant code with as few breaking changes as possible.

#### Breaking Changes:

- **CRITICAL** All module and folder names are now lower-case.
  + All `import PyISY` and `from PyISY import *` must be updated to `import pyisy` and `from pyisy import *`.
  + All class imports (e.g. `from PyISY.Nodes import Node` is now `from pyisy.nodes import Node`). Class names are still capitalized / CamelCase.
- A node Event is now returned as an object. In most cases this is a benefit because it returns more details than just the received command (value, uom, precision, etc), and it represents itself in string from the same as previously; however, direct comparisons will now fail unless updated:
    - "`event == "DON"`" must be replaced with "`event.event == "DON"`" or "`str(event) == "DON"`"
- Node Unit of Measure is returned as a string if it is not a list of UOMs, otherwise it is returned as a list. Previously this was returned as a 1-item list if there was only 1 UOM.
    - ISYv4 and before returned the UOM as a string ('%/on/off' or 'degrees'), ISYv5 phases this out and uses numerical UOMs that correspond to a defined value in the SDK (included in constants file).
    - Previous implementations of `unit = uom[0]` should be replaced with `unit = uom` and for compatibility, UOM should be checked if it is a list with `isinstance(uom, list)`.
    
    ```python
        uom = self._node.uom
        if isinstance(uom, list):
            uom = uom[0]
    ```
    
- Functions and properties have been renamed to snake_case from CamelCase.
  - Property `node.hasChildren` has been renamed to `node.has_children`.
  - Node Parent property has been renamed. Internal property is `node._parent_nid`, but externally accessible property is `node.parent_node`.
  - `node.controlEvents` has been renamed to `node.control_events`.
  - `variable.setInit` and `variable.set_value` have been renamed to `variable.set_init` and `variable.set_value`.
  - `ISY.sendX10` has been renamed to `ISY.send_x10_cmd`.
  - Network Resources `updateThread` function has been renamed to `update_threaded`.
  - Properties `nid`, `pid`, `nids`, `pids` have been renamed to `address` and `addresses` for consisitency. Variables still use `vid`; however, they also include an `address` property of the form `type.id`.
  - Node Functions `on()` and `off()` have been renamed to `turn_on()` and `turn_off()`
  - Node.lock() and Node.unlock() methods are now Node.secure_lock() and Node.secure_unlock().
  - Node climate and fan speed functions have been reduced and require a proper command from UOM 98/99 (see `constants.py`):
    + For example to activate PROGRAM AUTO mode, call `node.set_climate_mode("program_auto")`
  - Program functions have been renamed:
    + `runThen` -> `run_then`
    + `runElse` -> `run_else`
    + `enableRunAtStartup` -> `enable_run_at_startup`
    + `disableRunAtStartup` -> `disable_run_at_startup`

#### New:

- Major code refactoring to consolidate nested function calls, remove redundant code.
- Black Formatting and Linting to PEP8.
- Dynamically adds control functions to the Node and Program class--this is for future expansion to only add the appropriate commands to a given Node Type (e.g. don't add climate_mode to a light).
- Adding retries for failed REST calls to the ISY #46
- Adds increased Z-Wave support by storing the `devtype` category (since `type` is useless for Z-Wave)
- Expose UUID, Firmware, and Hostname properties for referencing inside the `isy` object.
- Various node commands have been renamed / newly exposed:
    + `start_manual_dimming`
    + `stop_manual_dimming`
    + `set_climate_setpoint`
    + `set_climate_setpoint_heat`
    + `set_climate_setpoint_cool`
    + `set_fan_speed`
    + `set_climate_mode`
    + `beep`
    + `brighten`
    + `dim`
    + `fade_down`
    + `fade_up`
    + `fade_stop`
    + `fast_on`
    + `fast_off`

#### Fixes:

- #22, #31, #32, #41, #43, #45, #46
- Malformed climate control commands
   - They were missing the `self._id` parameter, were missing a `.conn` in the command path and did not convert the values to strings before attempting to encode.
   - They are sending *2 for the temperature for ALL thermostats instead of just Insteon/UOM 101.
   - Several modes were missing for the Insteon Thermostats.
- Fix Node.aux_properties inconsistent typing #43 and now updates the existing aux_props instead of re-writing the entire dict.
- Zwave multisensor support #31 -- Partial Fix. [Forum Thread is here](https://community.home-assistant.io/t/isy994-z-wave-sensor-enhancements-testers-wanted/124188)
