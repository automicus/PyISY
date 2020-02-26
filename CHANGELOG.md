## CHANGELOG

### [v2.0.0] - Version 2.0 Initial Release

#### Summary: 

V2 is a significant refactoring and cleanup of the original PyISY code, with the primary goal of (1) fixing as many bugs in one shot as possible and (2) moving towards PEP8 compliant code with as few breaking changes as possible.

#### Breaking Changes:

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
    
- Node.lock() and Node.unlock() methods are now Node.secure_lock() and Node.secure_unlock().
- Most functions *that should be internal only* have been renamed to snake_case from CamelCase.
- Node Parent property has been renamed. Internal property is `node._parent_nid`, but externally accessible property is `node.parent_node`.

#### New:

- Major code refactoring to consolidate nested function calls, remove redundant code.
- Black Formatting and Linting to PEP8.
- Dynamically adds control functions to the Node and Program class--this is for future expansion to only add the appropriate commands to a given Node Type (e.g. don't add climate_mode to a light).
- Adding retries for failed REST calls to the ISY #46
- Adds increased Z-Wave support by storing the `devtype` category (since `type` is useless for Z-Wave)

#### Fixes:

- #22, #31, #32, #41, #43, #45, #46
- Malformed climate control commands
   - They were missing the `self._id` parameter, were missing a `.conn` in the command path and did not convert the values to strings before attempting to encode.
   - They are sending *2 for the temperature for ALL thermostats instead of just Insteon/UOM 101.
   - Several modes were missing for the Insteon Thermostats.
- Fix Node.aux_properties inconsistent typing #43 and now updates the existing aux_props instead of re-writing the entire dict.
- Zwave multisensor support #31 -- Partial Fix. [Forum Thread is here](https://community.home-assistant.io/t/isy994-z-wave-sensor-enhancements-testers-wanted/124188)
