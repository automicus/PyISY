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

# Install development dependencies
pip install -r requirements.txt -r requirements-dev.txt
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

## Releases

Detailed change logs are available on the [GitHub Releases](https://github.com/automicus/PyISY/releases) page.

## Credits

- Ryan Kraus ([@rmkraus]) - Creator
- Tim ([@shbatm]) - lead Maintainer
- Greg Laabs ([@overloadut]) - Maintainer

[@rmkraus]: https://github.com/rmkraus
[@shbatm]: https://github.com/shbatm
[@overloadut]: https://github.com/overloadut
