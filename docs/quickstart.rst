.. _tutorial:

PyISY Tutorial
==============

This is the basic user guide for the PyISY Python module.
This module was developed to communicate with the UDI ISY-994 home automation hub
via the hub's REST interface and Websocket/SOAP event streams. It provides
near real-time updates from the device and allows control of all devices that
are supported within the ISY.

The way this module works is by connecting to your device, gathering information about
the configuration and nodes connected, and then creating a local shadow structure that
mimics the ISY's internal structure; similar to how UDI's Admin Console works in Java.

Once connected, the module can then be used by other programs or Python scripts to
interact with the ISY and either a) get the status of a node, program, variable, etc.,
or b) run a command on those items.

.. note::

    This documentation is specific to PyISY Version 3.x.x, which uses asynchronous
    communications and the asyncio module. If you need threaded (synchronous) support
    please use Version 2.x.x.


Environment Setup
-----------------

This module can be installed via pip in any environment supporting Python 3.7 or later:

.. code-block:: shell

    pip3 install pyisy


Quick Start
~~~~~~~~~~~

Starting with Version 3, this module can connect directly from the the command line
to immediately print the list of nodes, and connect to the event stream and print
the events as they are sent from the ISY.

After installation, you can test the connection with the following

.. code-block:: shell

    python3 -m pyisy http://your-isy-url:80 username password

A good starting point for developing your own code is to copy the `__main__.py` file
from the module's source code. This walks you through how to create the connections and
some simple commands to get you started.

You can download it from GitHub: `<https://github.com/automicus/PyISY/blob/v3.x.x/pyisy/__main__.py>`_


Basic Usage
-----------

Testing Your Connection
~~~~~~~~~~~~~~~~~~~~~~~

When connecting to the ISY, it will connect and download all available information and populate
the local structures. Sometimes you just want to make sure the connection works before setting
everything up. This can be done using the :class:`Connection<pyisy.connection.Connection>` Class.

.. code-block:: python

    import asyncio
    import logging
    from urlparse import urlparse

    from pyisy import ISY
    from pyisy.connection import ISYConnectionError, ISYInvalidAuthError, get_new_client_session
    _LOGGER = logging.getLogger(__name__)

    """Validate the user input allows us to connect."""
    user = "username"
    password = "password"
    host = urlparse("http://isy994-ip-address:port/")
    tls_version = "1.2" # Can be False if using HTTP

    if host.scheme == "http":
        https = False
        port = host.port or 80
    elif host.scheme == "https":
        https = True
        port = host.port or 443
    else:
        _LOGGER.error("host value in configuration is invalid.")
        return False

    # Use the helper function to get a new aiohttp.ClientSession.
    websession = get_new_client_session(https, tls_ver)

    # Connect to ISY controller.
    isy_conn = Connection(
        host.hostname,
        port,
        user,
        password,
        use_https=https,
        tls_ver=tls_version,
        webroot=host.path,
        websession=websession,
    )

    try:
        with async_timeout.timeout(30):
            isy_conf_xml = await isy_conn.test_connection()
    except (ISYInvalidAuthError, ISYConnectionError):
        _LOGGER.error(
            "Failed to connect to the ISY, please adjust settings and try again."
        )

Once you have a connection class and successfully tested the configuration, you can
then use the :class:`Configuration<pyisy.configuration.Configuration>` Class to get
some additional details about the ISY, including the firmware version, name, and
installed options like Networking, Variables, or NodeServers.

.. code-block:: python

    try:
        isy_conf = Configuration(xml=isy_conf_xml)
    except ISYResponseParseError as error:
        raise CannotConnect from error
    if not isy_conf or "name" not in isy_conf or not isy_conf["name"]:
        raise CannotConnect


Connecting to the Controller
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Connecting to the controller is simple and will create an instance of
the :class:`ISY<pyisy.isy.ISY>` class. This instance is what we will use to interact with the
controller. By default when connecting to the ISY, it will load all available modules;
this means all of the Nodes, Scenes, Programs, and Variables. The
networking module will only be loaded if it is available.

As mentioned above, the best starting point for your own script is the
`__main__.py` file. This includes the basic connection to the ISY and also
connecting to the event stream.

Looking at the main function here, you can see the general flow:

1. Validate the settings
2. Create (or provide) an `asyncio` WebSession.
3. Create an instance of the :class:`ISY<pyisy.isy.ISY>` Class
4. Initialize the connection with :meth:`isy.initialize<pyisy.isy.ISY.initialize>`.
5. Connect to the :class:`WebSocketClient<pyisy.events.websocket.WebSocketClient>` for real-time event updates.
6. Safely shutdown the connection when done with :meth:`isy.shutdown()<pyisy.isy.shutdown>`.

.. literalinclude:: ../pyisy/__main__.py
    :language: python
    :pyobject: main

General Structure of the ISY Class
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The :class:`ISY<pyisy.isy.ISY>` Class holds the local "shadow" copy of the
ISY's structure and status. You can access the different components just like Python a `dict`.
Each category is a `dict`-like object that holds the structure, and then each
element is populated within that structure.

- Nodes & Groups (Scenes): :class:`isy.nodes<pyisy.nodes.Nodes>`
- Programs & Program Folders: :class:`isy.programs<pyisy.programs.Programs>`
- Variables: :class:`isy.variables<pyisy.variables.Variables>`
- Network Resources: :class:`isy.networking<pyisy.networking.NetworkResources>`
- Clock Info: :class:`isy.clock<pyisy.clock.Clock>`
- Configuration Info: :class:`isy.configuration<pyisy.configuration.Configuration>`


Controlling a Node on the Insteon Network
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Let's get straight into the fun by toggling a node on the Insteon
network. To interact with both Insteon nodes and scenes, the nodes
subclass is used. The best way to connect to a node is by using its
address directly. Nodes and folders on the ISY controller can also be
called by their name.

.. code:: python

    # interact with node using address
    NODE = '22 5C EB 1'
    node = isy.nodes[NODE]
    await node.turn_off()
    sleep(5)
    await node.turn_on()

.. code:: python

    # interact with node using name
    node = isy.nodes['Living Room Lights']
    await node.turn_off()
    sleep(5)
    await node.turn_on()

Controlling a Scene (Group) on the Insteon Network
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Just a small point of order here. The words Group and Scene are used
interchangeably on the ISY device and similarly in this library. Don't
let this confuse you.

Now, groups and nodes are controlled in nearly identical ways. They can
be referenced by either name or address.

.. code:: python

    # control scene by address
    SCENE = '28614'
    await isy.nodes[SCENE].turn_off()
    asyncio.sleep(5)
    await isy.nodes[SCENE].turn_on()

.. code:: python

    # control scene by name
    await isy.nodes['Downstairs Dim'].turn_off()
    asyncio.sleep(5)
    await isy.nodes['Downstairs Dim'].turn_on()

Controlling an ISY Program
~~~~~~~~~~~~~~~~~~~~~~~~~~

Programs work the same way. I feel like you are probably getting the
hang of this now, so I'll only show an example using an address. One
major difference between programs and nodes and groups is that with
programs, you can also interact directly with folders.

.. code:: python

    # controlling a program
    PROG = '005E'
    await isy.programs[PROG].run()
    asyncio.sleep(3)
    await isy.programs[PROG].run_else()
    asyncio.sleep(3)
    await isy.programs[PROG].run_then()

In order to interact with a folder as if it were a program, there is one
extra step involved.

.. code:: python

    PROG_FOLDER = '0061'
    # the leaf property must be used to get an object that acts like program
    await isy.programs[PROG_FOLDER].leaf.run()

Controlling ISY Variables
~~~~~~~~~~~~~~~~~~~~~~~~~

Variables can be a little tricky. There are integer variables and state
variables. Integer variables are called with a 1 and state variables are
called with a 2. Below is an example of both.

.. code:: python

    # controlling an integer variable
    var = isy.variables[1][3]
    await var.set_value(0)
    print(var.status)
    await var.set_value(6)
    print(var.status)


.. parsed-literal::

    0
    6


.. code:: python

    # controlling a state variable (Type 2) init value
    var = isy.variables[2][14]
    await var.set_init(0)
    print(var.init)
    await var.set_init(6)
    print(var.init)


.. parsed-literal::

    0
    6


Controlling the Networking Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is in the works and coming soon.

Event Updates
-------------

This library can subscribe to the ISY's Event Stream to receive updates
on devices as they are manipulated. This means that your program can
respond to events on your controller in real time using websockets and
a subscription-based event notification.

Subscribing to Updates
~~~~~~~~~~~~~~~~~~~~~~

.. warning::

    THIS DOCUMENTATION IS STILL A WORK-IN-PROGRESS. The details have not yet been updated
    for Version 2 or Version 3 of the PyISY Module. If you would like to help, please contribute
    on GitHub.

The ISY class will not be receiving updates by default. It is, however,
easy to enable, and it is done like so.

.. code:: python

    isy.auto_update = True

By default, PyISY will detect when the controller is no longer
responding and attempt a reconnect. Keep in mind though, it can take up
to two minutes to detect a lost connection. This means if you restart
your controller, in about two minutes PyISY will detect that, reconnect,
and update all the elements to their updated state. To turn off auto
reconnects, the following parameter can be changed.

.. code:: python

    isy.auto_reconnect = False

Now, once the connection is lost, it will stay disconnected until it is
told to reconnect.

Binding Events to Updates
~~~~~~~~~~~~~~~~~~~~~~~~~

Using the VarEvents library, we can bind functions to be called when
certain events take place. Subscribing to an event will return a handler
that we can use to unsubscribe later. For a full list of events, check
out the VarEvents documentation.

.. code:: python

    def notify(e):
        print('Notification Received')

    # interact with node using address
    NODE = '22 5C EB 1'
    node = isy.nodes[NODE]
    handler = node.status.subscribe('changed', notify)

Now, when we make a change to the node, we will receive the
notification...

.. code:: python

    node.status.update(100)


.. parsed-literal::

    Notification Received


Now we can unsubscribe from the event using the handler.

.. code:: python

    handler.unsubscribe()
    node.status.update(75)

More details about event handling are discussed inside the rest of the
documentation, but that is the basics.
