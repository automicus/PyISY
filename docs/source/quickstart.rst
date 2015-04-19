
PyISY Quick Start
=================

This is the basic user guide for the PyISY Python module. This file can
be downloaded and run locally to observe the actions first hand. In
order to run this Notebook locally, you'll have to create a settings
file in the same directory that the iPython Notebook file is placed.
I'll cover this more later. You'll also want to pay close attention to
the item addresses and names that are being called.

This Notebook can be downloaded `here. <http://docs.automic.us/PyISY/v1.0.0/PyISY.ipynb>`_

Environment Setup
-----------------

Basic Imports
~~~~~~~~~~~~~

To begin, we will import the PyISY library as well as a few others that
we will need later on.

.. code:: python

    import PyISY
    from time import sleep

Load Settings
~~~~~~~~~~~~~

If you are interested in running this notebook locally, you'll have to
create a file called PyISY.settings.txt. This file will contain all the
information needed to connect to the ISY device. This file must be four
lines and contain the IP address, port, username, and password needed to
connect to the ISY controller. It should look something like the
following.

.. parsed-literal::

    192.168.1.10
    80
    username
    password

.. code:: python

    # load settings
    f = open('PyISY.settings.txt', 'r')
    ADDR = f.readline().strip()
    PORT = f.readline().strip()
    USER = f.readline().strip()
    PASS = f.readline().strip()
    f.close()

Basic Usage
-----------

Connecting to the Controller
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Connecting to the controller is simple and will create an instance of
the ISY class. This instance is what we will use to interact with the
controller. To connect, use the following line. A lot of output will be
printed indicating everything that is happening behind the scenes.
Basically, what all this means is that an initial connection is being
made and then all of the available modules are being loaded. By default
this means all of the Nodes, Scenes, Programs, and Variables. If the
climate module is available, it will be loaded. Similarly, the
networking module will be loaded if it is available.

.. code:: python

    # connect to ISY
    isy = PyISY.ISY(ADDR, PORT, USER, PASS)
    print(isy.connected)

.. parsed-literal::

    True


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
    node.off()
    sleep(5)
    node.on()
.. code:: python

    # interact with node using name
    node = isy.nodes['Living Room Lights']
    node.off()
    sleep(5)
    node.on()

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
    isy.nodes[SCENE].off()
    sleep(5)
    isy.nodes[SCENE].on()
.. code:: python

    # control scene by name
    isy.nodes['Downstairs Dim'].off()
    sleep(5)
    isy.nodes['Downstairs Dim'].on()

Controlling an ISY Program
~~~~~~~~~~~~~~~~~~~~~~~~~~

Programs work the same way. I feel like you are probably getting the
hang of this now, so I'll only show an example using an address. One
major difference between programs and nodes and groups is that with
programs, you can also interact directly with folders.

.. code:: python

    # controlling a program
    PROG = '005E'
    isy.programs[PROG].run()
    sleep(3)
    isy.programs[PROG].runElse()
    sleep(3)
    isy.programs[PROG].runThen()

In order to interact with a folder as if it were a program, there is one
extra step involved.

.. code:: python

    PROG_FOLDER = '0061'
    # the leaf property must be used to get an object that acts like program
    isy.programs[PROG_FOLDER].leaf.run()

Controlling ISY Variables
~~~~~~~~~~~~~~~~~~~~~~~~~

Variables can be a little tricky. There are integer variables and state
variables. Integer variables are called with a 1 and state variables are
called with a 2. Below is an example of both.

.. code:: python

    # controlling an integer variable
    var = isy.variables[1][3]
    var.val = 0
    print(var.val)
    var.val = 6
    print(var.val)

.. parsed-literal::

    0
    6


.. code:: python

    # controlling a state variable
    var = isy.variables[2][14]
    var.val = 0
    print(var.val)
    var.val = 6
    print(var.val)

.. parsed-literal::

    0
    6


Interacting with the Climate Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This one is pretty straight forward. Everyone of the parameters can be
pulled in the same way.

.. code:: python

    # test climate
    print(repr(isy.climate))
    print(isy.climate.Dew_Point)
    print(isy.climate.Dew_Point_units)

.. parsed-literal::

    Climate Module
      Average_Temperature_Tomorrow = 0 
      Dew_Point = 0 
      Elevation = 0 
      Evapotranspiration = 0 
      Feels_Like = 0 
      Forecast_Average_Temperature = 0 
      Forecast_High_Temperature = 0 
      Forecast_Humidity = 0 
      Forecast_Low_Temperature = 0 
      Forecast_Rain = 0 
      Forecast_Snow = 0 
      Gust_Speed = 0 
      Gust_Speed_Tomorrow = 0 
      High_Temperature_Tomorrow = 0 
      Humidity = 0 
      Humidity_Tomorrow = 0 
      Irrigation_Requirement = 0 
      Light = 0 
      Low_Temperature_Tomorrow = 0 
      Pressure = 0 
      Rain_Tomorrow = 0 
      Snow_Tomorrow = 0 
      Temperature = 0 
      Temperature_Average = 0 
      Temperature_High = 0 
      Temperature_Low = 0 
      Total_Rain_Today = 0 
      Water_Deficit_Yesterday = 0 
      Wind_Direction = 0 
      Wind_Speed = 0 
      Wind_Speed_Tomorrow = 0 
    
    0
    


Controlling the Networking Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is in the works and coming soon.

Event Updates
-------------

This library can subscribe to the ISY's Event Stream to recieve updates
on devices as they are manipulated. This means that your program can
respond to events on your controller in real time. This is powered
primarily by the VarEvents library and I won't go too much into the
inner workings of that library here, but I'll give a quick overview of
using the events system.

Subscribing to Updates
~~~~~~~~~~~~~~~~~~~~~~

The ISY class will not be recieving updates by default. It is, however,
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

Now, when we make a change to the node, we will recieve the
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
