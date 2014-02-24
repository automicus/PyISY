"""
PyISY - Python Library for the ISY Controller

DESCRIPTION:
	This module is a set of Python bindings for the ISY's REST API. The
	ISY is developed by Universal Devices and is a home automation
	controller for Insteon and X10 devices.

 LICENSE:
    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.

AUTHOR: Humble Robot (Ryan M. Kraus)
COPYRIGHT: (C) 2013
WRITTEN: December, 2013
"""

from ISY import ISY
import tests

def install(*args, **kwargs):
    mod = ISY(*args, **kwargs)
    mod.auto_update = True
    return mod
