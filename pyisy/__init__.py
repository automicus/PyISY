"""
PyISY - Python Library for the ISY Controller.

This module is a set of Python bindings for the ISY's REST API. The
ISY is developed by Universal Devices and is a home automation
controller for Insteon and X10 devices.

Copyright 2015 Ryan M. Kraus
               rmkraus at gmail dot com

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from importlib.metadata import PackageNotFoundError, version

from .exceptions import (
    ISYConnectionError,
    ISYInvalidAuthError,
    ISYMaxConnections,
    ISYResponseParseError,
    ISYStreamDataError,
    ISYStreamDisconnected,
)
from .isy import ISY

try:
    __version__ = version("pyisy")
except PackageNotFoundError:
    __version__ = "unknown"

__all__ = [
    "ISY",
    "ISYInvalidAuthError",
    "ISYConnectionError",
    "ISYMaxConnections",
    "ISYResponseParseError",
    "ISYStreamDataError",
    "ISYStreamDisconnected",
]
__author__ = "Ryan M. Kraus"
__email__ = "rmkraus at gmail dot com"
__date__ = "February 2020"
