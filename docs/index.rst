PyISY Documentation
===================

Python Library for the ISY Controller
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This library allows for easy interaction with an ISY994 Controller from `UDI <https://www.universal-devices.com/>`_ allowing you to interact with nodes, programs, variables, and the network module through a python interface.
This class also allows for functions to be assigned as handlers when ISY parameters are changed. ISY parameters can be monitored automatically as changes are reported from the device.

Project Information
~~~~~~~~~~~~~~~~~~~

|  Docs: `ReadTheDocs <https://pyisy.readthedocs.io>`_
|  Source: `GitHub <https://github.com/automicus/PyISY>`_


Installation
~~~~~~~~~~~~

The easiest way to install this package is using pip with the command:

.. code-block:: bash

    pip install pyisy

Requirements
~~~~~~~~~~~~

This package requires three other packages, also available from pip. They are
installed automatically when PyISY is installed using pip.

* `requests <http://docs.python-requests.org/en/latest/>`_
* `dateutil <https://dateutil.readthedocs.io/en/stable/>`_
* `aiohttp <https://docs.aiohttp.org/en/stable/>`_

Contents
~~~~~~~~
.. toctree::
   :maxdepth: 1

   quickstart
   library
   constants

Indices and Tables
~~~~~~~~~~~~~~~~~~
* :ref:`genindex`
* :ref:`search`
