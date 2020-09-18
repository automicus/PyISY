#!/bin/bash

cd /workspaces/PyISY

# Setup the test_scripts folder as copy of the example.
mkdir test_scripts
cp -r pyisy/__main__.py test_scripts/example_connection.py

# Install the editable local package
pip3 install -e .

# Install pre-commit requirements
pre-commit install
