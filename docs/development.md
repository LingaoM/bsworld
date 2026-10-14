# Development and Unit Tests

[English](development.md) | [中文](zh-CH/development.md)

For local development, prepare dependencies and install BSWorld using the README's [local Linux setup](../README.md#local-linux), then run the commands below. For container test commands, see the [Docker guide](../docker/README.md#run-tests).

## Run Unit Tests

Run from the repository root:

```sh
cd "$BSWORLD_ROOT"
source .venv/bin/activate
pytest tests/unit -q
```

## Unit-Tested Contracts

The fast unit suites cover the framework contracts described in the README:

- CLI flags, output directories, xdist identity sharing, and `--no-hci-dump`: `tests/unit/test_plugin.py`
- Environment-selected artifact paths, BabbleSim binary/module readiness checks and native executable readiness checks: `tests/unit/test_env.py`, `tests/unit/test_artifact_paths.py`, and `tests/unit/test_dependency_readiness.py`
- Virtual Controller setup, Application registration, device ID allocation, and topology lifecycle: `tests/unit/test_topology.py` and `tests/unit/test_babblesim_backend.py`
- asyncio-compatible discrete time, callback and I/O ordering, clock protocol behavior, and FIFO-backed `wait_log`: `tests/unit/test_scheduler.py` and `tests/unit/test_runtime.py`
- Virtual Controller BTSnoop socket capture: `tests/unit/test_hci.py`
- RF interference and attenuation configuration: `tests/unit/test_interference.py` and `tests/unit/test_babblesim_backend.py`

Application behavior, RF propagation itself, and end-to-end Bluetooth LE examples are covered by the simulation suites under `tests/integration/*`.

## Unit Test Organization

Unit tests should cover stable behavior and module contracts, not incidental control flow. Prefer one focused assertion path per test and group tests by the subsystem they protect:

- `tests/unit/test_plugin.py`: pytest plugin options and session environment.
- `tests/unit/test_topology.py`: topology orchestration, generic process lifecycle, and Controller allocation.
- `tests/unit/test_babblesim_backend.py`: BabbleSim process arguments, device ID allocation, interference, trace conversion, and cleanup.
- `tests/unit/test_hci.py`: Virtual Controller BTSnoop socket capture.
- `tests/unit/test_scheduler.py`: event loop time switching, standard asyncio primitives, and I/O ordering.
- `tests/unit/test_bsim_clock.py`: FIFO registration, binary message encoding, connection and response timeouts, partial I/O, and disconnect handling.
- `tests/unit/test_runtime.py`: FIFO log capture and complete-line matching.
- `tests/unit/test_interference.py`: RF configuration validation.

`tests/integration/babblesim/test_babblesim_clock.py` exercises the Python clock against a real PHY, including resource cleanup, PHY disconnects, an unresponsive PHY, and a PHY killed before clock connection. It requires the normal BabbleSim build but no built Application or Controller.

Avoid tests that only pin private fallback order or implementation table ordering. If a behavior matters, name the test after the user-visible contract it protects.

## Linting

Use [Ruff](https://docs.astral.sh/ruff/) for Python linting:

```sh
ruff check src tests
ruff check --fix src tests
```

Configuration lives in `pyproject.toml` under `[tool.ruff]`.

## Documentation

Documentation is maintained as plain Markdown. English project documentation remains under `docs/`, while its Chinese translation is centralized under `docs/zh-CH/`. Component-specific README files under `components/` and `tests/` remain beside the component they describe, with Chinese files using the `.zh-CN.md` suffix.

Use the root README as the documentation entry point, and update the matching English/Chinese page together when behavior changes.

## Extending BSWorld

Most new Bluetooth LE Application environments only need a suite-local helper, tests beside the suite that owns them, and README build commands when native binaries are involved. Zephyr and NuttX keep their process launch contracts in their own integration directories because each environment has a different argv convention. Python stacks such as Bumble can run in pytest and connect directly to a Controller socket. Linux stacks such as BlueZ can run inside a QEMU Guest whose HCI UART is bridged to the same socket interface. Every registered Application receives an independent Virtual Controller.

Framework changes are needed only when the integration introduces a new execution contract:

- **Process launch convention**: add or extend a test-side adapter that creates a `ProcessInstance` with the platform's BabbleSim identity and HCI socket arguments, then exercise that adapter in the owning integration suite.
- **RF model wrapper**: add the public configuration type and validation in `src/bsworld/interference.py`, translate it to BabbleSim arguments in `src/bsworld/backends/babblesim.py`, and test both invalid input and generated commands.

Keep platform-specific profiles, source configuration, and build instructions with their test suite. Shared framework code should contain only behavior that is required by more than one Application environment or forms part of BSWorld's public execution model.

## Coverage

Branch coverage is provided by [coverage.py](https://coverage.readthedocs.io/) and enabled via `[tool.coverage.run]` in `pyproject.toml`.

```sh
# Unit-only coverage, fast and no firmware/BabbleSim required
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
python -m coverage run -m pytest \
  -p pytest_asyncio.plugin -p bsworld.plugin tests/unit
python -m coverage report

# Manual runtime dependency setup, then simulation without coverage instrumentation
pytest tests/integration/ -n auto
```

The unit coverage command starts coverage before pytest imports any project module, disables unrelated third-party plugin autoload, and then explicitly loads the asyncio and BSWorld plugins required by the test suite. The configured report covers the `bsworld` package, including its runtime scheduler.
