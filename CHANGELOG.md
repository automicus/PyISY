## CHANGELOG

### GitHub Release Versioning

As of v3.0.7, this module will document all changes within the GitHub release information to avoid duplication.

### [v3.0.6] Fix Group States for Stateless Controllers

- Fix Group States for Stateless Controllers (Fixes #256)
  - ControlLinc and RemoteLinc (v1) devices are excluded from group states to correctly reflect the state since these devices don't update
    the controller status unless a button is pushed.
- Bump pyupgrade from 2.31.0 to 2.31.1
- Bump pylint from 2.12.2 to 2.13.4
- Bump black from 22.1.0 to 22.3.0

### [v3.0.5] Forced Republish of Package

- No changes

### [v3.0.3] - Maintenance Release

- Prevent callback exception from disconnecting websocket (#248)

### [v3.0.2] - Unsubscribe on Lost Connection

- Attempt to unsubscribe instead of hard disconnect on non-critical socket errors (TCP Socket only, does not affect websockets).
- Bump pyupgrade from 2.29.1 to 2.31.0
- Update `.devcontainer` to latest VSCode Template
- Bump black from 21.12b0 to 22.1.0 (#247)

### [v3.0.1] - Fix Unsubscribe SOAP Message and Dependency Updates

- Bump codespell from 2.0.0 to 2.1.0 (#195)
- Bump flake8 from 3.9.2 to 4.0.1 (#229)
- Bump isort from 5.8.0 to 5.10.1 (#232)
- Bump pyupgrade from 2.16.0 to 2.29.1 (#234)
- Bump black from 21.5b1 to 21.12b0 (#238)
- Bump pylint from 2.8.2 to 2.12.2 (#239)
- Fixed Unsubscribe soap body (#240)

### [v3.0.0] - Async All the Things

#### Breaking Changes

- Module now uses asynchronous communications via `asyncio` and `aiohttp` for communicating with the ISY. Updates are required to run the module in an asyncio event loop.
- Connection with the ISY is no longer automatically initialized when the `ISY` or `Connection` classes are initialized. The `await isy.initialize()` function must be called when ready to connect. To test a connection only, you can use `Connection.test_connection()` after initializing at least a `Connection` class.
- When sending a command, the node status is no longer updated presumptively using a `hint` value. If you are not using either the websocket or event stream, you will need to manually call `node.update(wait_time=UPDATE_INTERVAL)` for the node after calling the `node.send_cmd()` to update the value of the node (#155).
- Group/Scene Status now excludes the state of any Insteon battery powered devices (on ISYv5 firmware only). These devices often have stale states and only update when they change, not when other controllers in the scene change; this leads to incorrect or misleading Group/Scene states (#156).

#### Changed

- Module can now be used/tested from the command-line with the new `__main__.py` script; you can test a connection with `python3 -m pyisy http://your-isy-url:80 username password`.
- Module now supports using the Websocket connections to the ISY instead of a SOAP-message based socket. This can be enabled by setting the `use_websocket=True` keyword parameter when initializing the `ISY()` class.
- A new helper function has been added to create an `aiohttp.ClientSession` compliant with the ISY: `Connection.get_new_client_session(use_https, tls_ver=1.1)` will return a web session that can be passed to the init functions of `ISY` and `Connection` classes.
- Add support for setting and retrieving Z-Wave Device Parameters using `node.set_zwave_parameter()` and `node.get_zwave_parameter()`.
- Allow renaming of nodes and groups for ISY v5.2.0 or later using the `node.rename()` method (#157).
- Add a folder property to each node and group (#159)
- Force UTF-8 decoding of responses and ignore errors (#126)
- Re-instate Documentation via Sphinx and ReadTheDocs (#150) (still a work in progress...)
- Fix Group All On improper reporting (7a4b3b4)
- Add DevContainer for development in VS Code.

### [v2.1.0] - Property Updates, Timestamps, Status Handling, and more...

#### Breaking Changes

- `Node.dimmable` has been depreciated in favor of `Node.is_dimmable` to make the naming more consistent with `is_lock` and `is_thermostat`. `Node.dimmable` will still work, however, plan for it to be removed in the future.
- `Node.is_dimmable` will only include the first subnode for Insteon devices in type 1. This should represent the main (load) button for KeypadLincs and the light for FanLincs, all other subnodes (KPL buttons and Fan Motor) are not dimmable (fixes #110)
- This removes the `log=` parameter when initializing new `Connection` and `ISY` class instances. Please update any loading functions you may use to remove this `log=` parameter.

#### Changed / Fixed

- Changed the default Status Property (`ST`) unit of measurement (UOM) to `ISY_PROP_NOT_SET = "-1"`: Some NodeServer and Z-Wave nodes do not make use of the `ST` (or status) property in the ISY and only report `aux_properties`; in addition, most NodeServer nodes do not report the `ST` property when all nodes are retrieved, they only report it when queried directly or in the Event Stream. Previously, there was no way to differentiate between Insteon Nodes that don't have a valid status yet (after ISY reboot) and the other types of nodes that don't report the property correctly since they both reported `ISY_VALUE_UNKNOWN`. The `ISY_PROP_NOT_SET` allows differentiation between the two conditions based on having a valid UOM or not. Fixes #98.
- Rewrite the Node status update receiver: currently, when a Node's status is updated, the `formatted` property is not updated and the `uom`/`prec` are updated with separate functions from outside of the Node's class. This updates the receiver to pass a `NodeProperty` instance into the Node, and allows the Node to update all of it's properties if they've changed, before reporting the status change to the subscribers. This makes the `formatted` property actually useful.
- Logging Cleanup: Removes reliance on `isy` parent objects to provide logger and uses a module-wide `_LOGGER`. Everything will be logged under the `pyisy` namespace except Events. Events maintains a separate logger namespace to allow targeting in handlers of `pyisy.events`.

#### Added

- Added `*.last_update` and `*.last_changed` properties which are UTC Datetime Timestamps, to allow detection of stale data. Fixes #99
- Add connection events for the Event Stream to allow subscription and callbacks. Attach a callback with `isy.connection_events(callback)` and receive a string with the event detail. See `constants.py` for events starting with prefix `ES_`.
- Add a VSCode Devcontainer based on Python 3.8
- Update the package requirements to explicitly include dateutil and the dev requirements for pre-commit
- Add pyupgrade hook to pre-commit and run it on the whole repo.

#### All PRs in this Version:

- Revise Node.dimmable property to exclude non-dimmable subnodes (#122)
- Logging cleanup and consolidation (#106)
- Fix #109 - Update for events depreciation warning
- Add Devcontainer, Update Requirements, Use PyUpgrade (#105)
- Guard against overwriting known attributes with blanks (#112)
- Minor code cleanups (#104)
- Fix Property Updates, Add Timestamps, Unused Status Handling (#100)
- Fix parameter name (#102)
- Add connection events target (#101)

#### Dependency Changes:

- Bump black from 19.10b0 to 20.8b1
- Bump pyupgrade from 2.3.0 to 2.7.2
- Bump codespell from 1.16.0 to 1.17.1
- Bump flake8 from 3.8.1 to 3.8.3
- Bump pydocstyle from 5.0.2 to 5.1.1
- Bump pylint from 2.4.4 to 2.6.0
- Bump isort from 4.3.21 to 5.5.2

### [v2.0.2] - Version 2.0 Initial Release

#### Summary:

V2 is a significant refactoring and cleanup of the original PyISY code, with the primary goal of (1) fixing as many bugs in one shot as possible and (2) moving towards PEP8 compliant code with as few breaking changes as possible.

#### Breaking Changes:

- **CRITICAL** All module and folder names are now lower-case.
  - All `import PyISY` and `from PyISY import *` must be updated to `import pyisy` and `from pyisy import *`.
  - All class imports (e.g. `from PyISY.Nodes import Node` is now `from pyisy.nodes import Node`). Class names are still capitalized / CamelCase.
- A node Event is now returned as an `NodeProperty(dict)` object. In most cases this is a benefit because it returns more details than just the received command (value, uom, precision, etc); direct comparisons will now fail unless updated:
  - "`event == "DON"`" must be replaced with "`event.control == "DON"`"
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
    - For example to activate PROGRAM AUTO mode, call `node.set_climate_mode("program_auto")`
  - Program functions have been renamed:
    - `runThen` -> `run_then`
    - `runElse` -> `run_else`
    - `enableRunAtStartup` -> `enable_run_at_startup`
    - `disableRunAtStartup` -> `disable_run_at_startup`
- Climate Module Retired as per [UDI Announcement](https://www.universal-devices.com/byebyeclimatemodule/)
- Remove dependency on VarEvents library
  - Calling `node.status.update(value)` (non-silent) to require the ISY to update the node has been removed. Use the proper functions (e.g. `on()`, `off()`) to request the ISY update. Note: all internal functions previously used `silent=True` mode.
  - Variables `val` property is now `status` for consistency.
  - Variables `lastEdit` property is now `last_edited` and no longer fires events on its own. Use a single subscriber to pick up changes to `status`, `init`, and `ts`.
  - Group All On property no longer first its own event. Subscribe to the status events for changes.
  - Subscriptions for status changes need to be updated:
    ```python
    # Old:
    node.status.subscribe("changed", self.on_update)
    # New:
    node.status_events.subscribe(self.on_update)
    ```
  - Program properties no longer fire their own events, but will fire the main status_event when something is changed.
  - Program property changes to conform to snake_case.
    - `lastUpdate` -> `last_update`
    - `lastRun` -> `last_run`
    - `lastFinished` -> `last_finished`
    - `runAtStartup` -> `run_at_startup`

#### New:

- Major code refactoring to consolidate nested function calls, remove redundant code.
- Black Formatting and Linting to PEP8.
- Modification of the `Connection` class to allow initializing a connection to the ISY and making calls externally, without the need to initialize a full `ISY` class with all properties.
- Adding retries for failed REST calls to the ISY #46
- Add support for ISY Portal (incl. multiple ISYs):
  - Initialize the connection with:
  ```python
  isy = ISY(
      address="my.isy.io",
      port=443,
      username="your@portal.email",
      password="yourpassword",
      use_https=True,
      tls_ver=1.1,
      log=None,
      webroot="/isy/unique_isy_url_code_from_portal",
  )
  # Unique URL can be found in ISY Portal under
  #   Tools > Information > ISY Information
  ```
- Adds increased Z-Wave support by returning Z-Wave Properties under the `Node.zwave_props` property:
  - `category`
  - `devtype_mfg`
  - `devtype_gen`
  - `basic_type`
  - `generic_type`
  - `specific_type`
  - `mfr_id`
  - `prod_type_id`
  - `product_id`
- Expose UUID, Firmware, and Hostname properties for referencing inside the `isy` object.
- Various node commands have been renamed / newly exposed:
  - `start_manual_dimming`
  - `stop_manual_dimming`
  - `set_climate_setpoint`
  - `set_climate_setpoint_heat`
  - `set_climate_setpoint_cool`
  - `set_fan_speed`
  - `set_climate_mode`
  - `beep`
  - `brighten`
  - `dim`
  - `fade_down`
  - `fade_up`
  - `fade_stop`
  - `fast_on`
  - `fast_off`
- In addition to the `node.parent_node` which returns a `Node` object if a node has a primary/parent node other than itself, there is now a `node.primary_node` property, which just returns the address of the primary node. If the device/group _is_ the primary node, this is the same as the address (this is the `pnode` tag from `/rest/nodes`).
- Expose the ISY Query Function (`/rest/query`) as `isy.query()`

#### Fixes:

- #11, #19, #22, #23, #31, #32, #41, #43, #45, #46, #51, #55, #59, #60, #82, #83
- Malformed climate control commands
  - They were missing the `self._id` parameter, were missing a `.conn` in the command path and did not convert the values to strings before attempting to encode.
  - They are sending \*2 for the temperature for ALL thermostats instead of just Insteon/UOM 101.
  - Several modes were missing for the Insteon Thermostats.
- Fix Node.aux_properties inconsistent typing #43 and now updates the existing aux_props instead of re-writing the entire dict.
- Zwave multisensor support #31 -- Partial Fix. [Forum Thread is here](https://community.home-assistant.io/t/isy994-z-wave-sensor-enhancements-testers-wanted/124188)
