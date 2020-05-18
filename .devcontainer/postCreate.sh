#!/bin/bash

cd /workspaces/PyISY

# Setup the test_scripts folder as copy of the examples.
mkdir test_scripts
cp -r examples/* test_scripts/

# Install the editable local package
pip3 install -e .

# Install pre-commit requirements
pre-commit install
