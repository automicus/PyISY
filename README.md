# PyISY

Python library for the Universal Devices ISY-994, Polisy, and eisy controllers.

This library allows for easy interaction with ISY nodes, programs, variables, and the network module. It provides asynchronous communication and supports near real-time updates via WebSocket or SOAP event streams.

The full documentation is available at [https://pyisy.readthedocs.io](https://pyisy.readthedocs.io).

## Features

- Asynchronous communication via `asyncio` and `aiohttp`.
- Support for ISY-994 (v4 and v5 firmware), Polisy, and eisy.
- Automatic updates from the device via WebSocket or SOAP.
- Interaction with nodes, groups, programs, variables, and networking modules.
- Command-line interface for quick testing and monitoring.

## Installation

```shell
pip install pyisy
```

## Quick Start

You can test the connection to your ISY directly from the command line:

```shell
python3 -m pyisy http://your-isy-url:port username password
```

### Basic Usage

```python
import asyncio
from pyisy import ISY


async def main():
    # Connect to ISY controller
    isy = ISY("192.168.1.10", 80, "admin", "password")

    # Initialize the connection and download information
    await isy.initialize()

    # Get a node by its address
    node = isy.nodes["1A 2B 3C 1"]
    print(f"Node Name: {node.name}")
    print(f"Node Status: {node.status}")

    # Turn a node on
    await node.turn_on()

    # Shutdown the connection
    await isy.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
```

## Development

Contributions are welcome! This project uses `pre-commit` to ensure code quality.

### Setup

```shell
# Clone the repository
git clone https://github.com/automicus/PyISY.git
cd PyISY

# Install development + test dependencies
pip install -r requirements.txt -r requirements-dev.txt -r requirements-test.txt
pip install -e .

# Install pre-commit hooks
pre-commit install
```

We use `ruff` for formatting and linting. You can run it manually:

```shell
ruff check .
ruff format .
```

A VSCode DevContainer is also provided for a consistent development environment.

### Tests

PyISY has an offline `pytest` suite covering the XML parsers, connection
behavior, the full `ISY.initialize()` lifecycle, and the per-node /
per-program action methods used by the Home Assistant `isy994`
integration. The fixtures are anonymized real-controller exports —
running the suite needs no live ISY.

**Please run the tests before opening a PR.** They are fast (~10 s) and
catch most regressions in the public API that Home Assistant Core
depends on.

```shell
# Run the full suite
pytest

# Run with a coverage report
pytest --cov=pyisy --cov-report=term-missing

# Run a single file or test
pytest tests/test_nodes.py
pytest tests/test_climate_lock.py::test_set_climate_setpoint_heat_doubles_for_uom_101
```

The same `pytest` job runs in CI on Python 3.11 and 3.14 (matching the
range Home Assistant supports). The terminal coverage report is visible
in the workflow logs.

If you change parsing or status behavior, be ready to refresh snapshots:

```shell
pytest --snapshot-update
```

Snapshots live under `tests/__snapshots__/` and are tracked in git.

## Releases

Detailed change logs are available on the [GitHub Releases](https://github.com/automicus/PyISY/releases) page.

## Credits

- Ryan Kraus ([@rmkraus]) - Creator
- Tim ([@shbatm]) - lead Maintainer
- Greg Laabs ([@overloadut]) - Maintainer

[@rmkraus]: https://github.com/rmkraus
[@shbatm]: https://github.com/shbatm
[@overloadut]: https://github.com/overloadut
