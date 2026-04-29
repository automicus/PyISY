# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

**PyISY** is the original async Python library for Universal Devices ISY-994 / IoX controllers (Polisy, eisy). It is the upstream package on PyPI (`pyisy`) used by the Home Assistant Core `isy994` integration. This is the `v3.x.x` branch (asyncio + aiohttp). The threaded `v2.x.x` branch is no longer the default.

This package has a successor, **PyISYoX**, which is a from-scratch rewrite by the v3 contributor with a different API (entity model, `ISYConnectionInfo` dataclass, helpers/ submodule, etc.). The HACS beta integration `hacs-isy994` consumes PyISYoX. **Do not import PyISYoX patterns into PyISY** — keep the public API stable since Home Assistant Core depends on it.

## Commands

```bash
# Install dev dependencies + editable install
pip install -r requirements.txt -r requirements-dev.txt
pip install -e .

# Set up pre-commit (CI runs the same)
pre-commit install
pre-commit run --all-files

# Smoke-test against a real ISY (also a usable script template)
python3 -m pyisy http://your-isy-url:80 username password
python3 -m pyisy -h         # full options
python3 -m pyisy -v ...     # verbose logging
python3 -m pyisy -q ...     # no event stream
python3 -m pyisy -n ...     # also load node servers

# Build docs
cd docs && make html
```

There is **no test suite** in this repo (the `tests/` directory does not exist; `pyproject.toml` references it for future use). CI runs only pre-commit (`.github/workflows/ci.yml`). When changing behavior, validate against a real ISY via `python3 -m pyisy ...` — there is no offline harness.

Lint stack (all run by pre-commit):

- **ruff** (lint + format) — config in `pyproject.toml`, target `py39`, line length 110
- **pyupgrade** (`--py39-plus`)
- **codespell** with an ISY-specific ignore list (`isy`, `nid`, `dof`, `don`, `BATLVL`, etc. — extend it if codespell flags a real ISY term)
- **yamllint**, **prettier**

## Architecture

### Entry point and lifecycle

`pyisy/isy.py` — the `ISY` class is the single object users construct. Construction does **no** I/O. `await isy.initialize()` is required and performs:

1. `conn.test_connection()` → parses `/rest/config` into a `Configuration`.
2. If the model is **not** `ISY 994`, calls `conn.increase_available_connections()` — IoX hardware allows far more concurrent connections than ISY-994 (the connection semaphore is sized accordingly in `connection.py`).
3. Fires off `asyncio.gather()` for status, time, nodes, programs, variable defs, variables, and (conditionally) network resources, then constructs `Clock`, `Nodes`, `Programs`, `Variables`, `NetworkResources` from the resulting XML.
4. `await self.nodes.update(xml=...)` applies status to nodes.

`await isy.shutdown()` stops the websocket / event stream and closes the aiohttp session.

### Connection layer (`connection.py`)

`Connection` owns the aiohttp session and **all** REST I/O. Notable details:

- Uses an asyncio Semaphore to enforce ISY-994's strict simultaneous-connection limit (2 HTTPS / 5 HTTP); `increase_available_connections()` raises it for IoX.
- `request()` handles retries with backoff, swallows expected 404s when `ok404=True`, and force-decodes responses as UTF-8 with `errors="ignore"` (ISY firmware emits invalid UTF-8 in some node names — see CHANGELOG #126).
- `get_new_client_session(use_https, tls_ver)` and `get_sslcontext()` are module-level helpers because the ISY-994 supports legacy TLS 1.1 and weak ciphers; consumers (HA Core) need to obtain a session compatible with the device.

### Event streams (`events/`)

Two mutually-exclusive transports for real-time updates:

- **`websocket.WebSocketClient`** — preferred, opt in via `ISY(use_websocket=True)`. Started/stopped explicitly with `isy.websocket.start()` / `.stop()`.
- **`tcpsocket.EventStream`** — legacy SOAP-over-TCP socket subscription. Lazily constructed when `isy.auto_update = True` is set. Reconnect is handled by a daemon `Thread` (`_auto_reconnecter` in `isy.py`) that recreates the `EventStream` on disconnect.

Setting `auto_update` while websockets are enabled is a no-op with a warning — the two paths must not be mixed. Connection-state notifications go through `isy.connection_events` (an `EventEmitter`) using the `ES_*` constants (`ES_CONNECTED`, `ES_RECONNECTING`, `ES_RECONNECT_FAILED`, etc.).

`eventreader.ISYEventReader` parses raw event XML; the `ISY` class itself dispatches `system_status_changed_received()` and node manager `_node_changed_received()` from parsed events.

### Platform managers

Each platform module is a dict-like collection that owns its entities and exposes an `EventEmitter` for changes:

- `nodes/` — `Nodes` manages both `Node` (devices) and `Group` (scenes); `nodebase.NodeBase` is the shared base. `NodeChangedEvent` (in `nodes/__init__.py`) is the payload published on `isy.nodes.status_events`. Group/Scene status excludes Insteon battery devices and stateless controllers (ControlLinc / RemoteLinc v1) — see CHANGELOG #156, #256.
- `programs/` — `Programs` indexes both `Program` and `programs.folder.Folder`. Folders expose a `.leaf` property used to invoke folder-level run actions.
- `variables/` — `Variables` is a 2-level mapping: `isy.variables[type][id]` where type `1` = integer, `2` = state.
- `networking.NetworkResources` / `NetworkCommand` — only loaded when `Configuration[CONFIG_NETWORKING]` or `CONFIG_PORTAL` is set.
- `node_servers.NodeServers` — Polyglot node server definitions; loaded only if `with_node_servers=True` is passed to `initialize()`.
- `clock.Clock` — derived from `/rest/time`; provides sunrise/sunset/tz info.
- `configuration.Configuration` — dict-like wrapper around the parsed `/rest/config` XML; consult it for feature flags before triggering optional REST calls.

### Helpers, constants, logging

- `helpers.py` contains `EventEmitter` / `EventListener` (the pub/sub primitives every manager uses) plus the XML-walking utilities (`value_from_xml`, `attr_from_xml`, `attr_from_element`, …). Most parsing in this codebase still uses `xml.dom.minidom` directly.
- `constants.py` is large (commands, URLs, UOM tables, node families, system-status codes, `ES_*` connection events, `NODE_CHANGED_ACTIONS`, `X10_COMMANDS`). Add new constants here rather than scattering literals.
- `logging.py` — `_LOGGER` is the package-wide logger under the `pyisy` namespace; events use a separate `pyisy.events` logger so consumers can filter. Call `enable_logging()` once at startup.

## Conventions when editing

- **Public API stability**: `pyisy.ISY`, `pyisy.connection.Connection`, the manager classes, and the `ISY*Error` exceptions in `pyisy/__init__.py` are consumed by Home Assistant Core. Renaming or changing signatures is a breaking change. If you find yourself wanting a different shape, that work belongs in PyISYoX, not here.
- **No presumptive status updates**: since v3.0.0, sending a command does not optimistically update `node.status`. Consumers that don't run an event stream are expected to call `node.update(wait_time=UPDATE_INTERVAL)` themselves.
- **UOM/precision sentinel**: `ISY_PROP_NOT_SET = "-1"` distinguishes "node has no ST property" from `ISY_VALUE_UNKNOWN` ("status not yet reported"). Don't conflate them — see CHANGELOG v2.1.0 #98.
- **XML decoding**: always go through `Connection.request()` so the UTF-8-with-ignore decode is applied. Don't read aiohttp responses directly.
- **Ruff ignores in `pyproject.toml`** are deliberate (e.g. `S101`, `SLF001`, `PLR091*`); don't try to fix what's listed there as part of unrelated work.

## Branches

- `v3.x.x` — current default branch; async, what every consumer ships.
- `v2.x.x` — legacy synchronous/threaded line; only fix here if explicitly asked.

## External resources

- ReadTheDocs: https://pyisy.readthedocs.io
- Source: https://github.com/automicus/PyISY
- Successor library: PyISYoX (separate repo) — different package name, different API.
- Downstream consumer: Home Assistant Core `isy994` integration.
