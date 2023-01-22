## CHANGELOG

### GitHub Release Versioning

As of v3.0.7, this module will document all changes within the GitHub release information to avoid duplication.

### [v3.2.0] Breaking Changes

#### Minimum Python Version

- Dropped support for <3.9
- Dropped support for ISY versions <4.3

- `NodeBase` `._id` attribute renamed to `_address`, continue to use `address` property.
- `Folder` `._id` attribute renamed to `_address`, continue to use `address` property.

#### Nodes

- No longer support direct setting of `status` property, use `update_status`
- `parse_xml_properties` moved from `pyisy.helpers` -> `pyisy.nodes.parser`
- Prec renamed to Precision
- type renamed to type\_
- removed dimmable property (use is_dimmable)
- GetChildren removed from `pyisy.nodes`
- Get_groups moved `pyisy.nodes.node` -> `pyisy.nodes`
- Event receiver functions moved to `pyisy.nodes.node_events`
- Get folder returns a named tuple `(name, address)`
- FAMILY\_\* moved to strenum
- PROTO\_\* moved to strenum

#### Programs

- No longer support direct setting of `last_edited` property, use `update_last_edited`
- No longer support direct setting of `status` property, use `update_status`

#### Variables

- No longer support direct setting of `status` property, use `update_status`
- Status represents raw values correctly, do not double convert
- prec renamed to precision and returns an `int`
- init renamed to initial
- vid renamed to variable_id

#### Helpers

- Moved to folder, default imports still work except:
- `EventEmitter`, `EventListener` moved to `pyisy.helpers.events`
- `NodeChangedEvent` moved from `pyisy.nodes` -> `pyisy.helpers.events`
- `NodeProperty`, `ZWaveProperties` moved to `pyisy.helpers.models`
- `value_from_xml`,`attr_from_xml`,`attr_from_element`,`value_from_nested_xml` moved to `pyisy.helpers.xml`, but still importable from `pyisy.helpers`
- `ntp_to_system_time` moved to `pyisy.clock`
  ZWaveProps `category` -> `cat` and return values as hex strings `0x0000`

#### Networking

- `._id` attribute renamed to `_address`, continue to use `address` property.

### Clock

- `Clock` information changed to dataclass `ClockData`, requires calling `.from_xml` instead of passing xml on init.
- New `Clock` init split to separate class. Must call `update()` after creating class.
- `Connection`.`get_clock` moved to `Clock`.`get_resource`

### Connections

- Use new `ISYConnectionInfo` class to build connection info
- TLS Version set to None will auto-negotiate (newer models)
- use_websocket is default True

### ISY Root

    Removed:
        port,
        use_https=False,
        webroot="",

Moved to helpers.session:
get_new_client_session
get_sslcontext
can_https

`conf` and `configuration` -> `config`

Intialiization can set options for what to load

### Configuration

no support for passing xml
change to data class
features moved to `Configuration.features`
networking is top-level

### Auto-update

You must manually refresh the platform after sending command when using auto_update=false

### Event Listeners:

isy.connection_events
isy.programs.status_events
isy.variables.status_events
isy.nodes.status_events
isy.status_events
isy.nodes.update_received
isy.nodes.control_message_received
isy.nodes.node_changed_received

## Home Assistant User Breaking Changes

- Programs: `last_finished`->`last_finished_time`, `last_run`->`last_run_time`
