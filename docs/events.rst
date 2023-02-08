PyISY Events
============

General Information
~~~~~~~~~~~~~~~~~~~

Several of the different classes in the module provide an :class:`~pyisy.helpers.events.EventEmitter` which allows you to subscribe to push updates about the class.

Available Emitters
~~~~~~~~~~~~~~~~~~

ISY Class
---------

isy.status_events - System-level status events (Busy/Not Busy)
isy.connection_events - System-level connection events (Connected/Disconnected)
isy.websocket.router.events - Direct access to all events received from websocket
isy._events.router.events - Direct access to all events received from TCP socket

Entity Platforms
----------------

isy.nodes.platform_events - Platform-level events, such as new/changed node configurations
isy.nodes.status_events - Individual entity status & control events for all entities
isy.nodes.entities["address"].status_events - Individual entity status events
isy.nodes.entities["address"].control_events - Individual entity control events

isy.programs.platform_events
isy.programs.status_events
isy.variables.platform_events
isy.variables.status_events
