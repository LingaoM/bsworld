# Development and Unit Tests

[English](development.md) | [中文](zh-CH/development.md)

Development and test commands require Python 3.12 or newer. Create the project virtual environment and install the dev extra first:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Unit-Tested Contracts

The fast unit suites cover the framework contracts described in the README:

- CLI flags, output directories, xdist identity sharing, and `--no-hci-dump`: `tests/unit/test_plugin.py`
- Shared `/tmp/bsworld/build/` paths, explicit BabbleSim readiness checks, official BabbleSim `make everything` setup expectations, and expanded prebuilt runtime checks: `tests/unit/test_env.py` and `tests/unit/test_dependency_readiness.py`
- Virtual Controller setup, Application registration, device ID allocation, and topology lifecycle: `tests/unit/test_topology.py` and `tests/unit/test_babblesim_backend.py`
- asyncio-compatible discrete time, callback and I/O ordering, clock protocol behavior, and FIFO-backed `wait_log`: `tests/unit/test_scheduler.py` and `tests/unit/test_runtime.py`
- Virtual Controller BTSnoop socket capture: `tests/unit/test_hci.py`
- RF interference and attenuation configuration: `tests/unit/test_interference.py` and `tests/unit/test_babblesim_backend.py`
- Test-profile runtime discovery, expanded Exodus runtime creation, release checksum validation, repository-relative installation, and release layout validation: `tests/unit/test_binary_release.py`

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
- `tests/unit/test_binary_release.py`: test-profile runtime discovery, expanded Exodus runtime creation, and binary release installation.

`tests/integration/babblesim/test_babblesim_clock.py` exercises the Python clock against a real PHY, including resource cleanup, PHY disconnects, an unresponsive PHY, and a PHY killed before clock connection. It requires the normal BabbleSim build but no prebuilt Application or Controller.

Avoid tests that only pin private fallback order or implementation table ordering. If a behavior matters, name the test after the user-visible contract it protects.

## Linting

Use [Ruff](https://docs.astral.sh/ruff/) for Python linting:

```sh
ruff check scripts src tests
ruff check --fix scripts src tests
```

Configuration lives in `pyproject.toml` under `[tool.ruff]`.

## Documentation

Documentation is maintained as plain Markdown. English project documentation remains under `docs/`, while its Chinese translation is centralized under `docs/zh-CH/`. Component-specific README files under `components/` and `tests/` remain beside the component they describe, with Chinese files using the `.zh-CN.md` suffix.

Use the root README as the documentation entry point, and update the matching English/Chinese page together when behavior changes.

## Extending BSWorld

Most new Bluetooth LE Application environments only need a suite-local helper, tests beside the suite that owns them, and a build script when native binaries are involved. Zephyr and NuttX keep their process launch contracts in their own integration directories because each environment has a different argv convention. Python stacks such as Bumble can run in pytest and connect directly to a Controller socket. Linux stacks such as BlueZ can run inside a QEMU Guest whose HCI UART is bridged to the same socket interface. Every registered Application receives an independent Virtual Controller.

Framework changes are needed only when the integration introduces a new execution contract:

- **Process launch convention**: add or extend a test-side adapter that creates a `ProcessInstance` with the platform's BabbleSim identity and HCI socket arguments, then exercise that adapter in the owning integration suite.
- **RF model wrapper**: add the public configuration type and validation in `src/bsworld/interference.py`, translate it to BabbleSim arguments in `src/bsworld/backends/babblesim.py`, and test both invalid input and generated commands.

Keep platform-specific profiles, source configuration, and build instructions with their test suite. Shared framework code should contain only behavior that is required by more than one Application environment or forms part of BSWorld's public execution model.

## Prebuilt Builds and Packaging

The Virtual Controller and firmware images use expanded [Exodus](https://pypi.org/project/exodus-bundler/) runtime trees. The `dev` extra installed above provides the pinned Exodus release and its Python 3.12 compatibility dependency.

Each dependency or test suite owns its `build.sh` and generated `prebuilt/` directory. Build one suite with its local entry point, one platform with its platform entry point, or all artifacts from the repository root:

```sh
python scripts/build_all.py \
  --nuttx-dir /path/to/nuttx \
  --nuttx-apps-dir /path/to/nuttx-apps \
  --zephyr-workspace /path/to/zephyrproject \
  --bsim-out-dir /tmp/bsworld/build/babblesim/bsim
```

All external workspace paths are explicit command-line arguments. The top-level Python builder invokes the platform-owned shell entry points in dependency order. `scripts/runtime_assets.py` imports the `devices.py` modules under `tests/`, discovers managed profile objects with `name` and `path` attributes, and adds the Virtual Controller declared by BSWorld itself. The platform scripts configure and compile their source, ask Exodus to collect the executable and runtime dependencies, and keep the resulting directory beside the owning suite. No intermediate per-image archive is created. Test execution never rebuilds or extracts firmware; it launches the configured `prebuilt/<name>/exodus/bin/*` executable directly.

A release-managed executable therefore needs at least one module-level profile object with `name` and `path` in the suite's `devices.py`. Repository paths below `prebuilt/` are collected automatically, while external programs are left outside the release. Profiles that share one executable are deduplicated, and the generated manifest records every profile that references it. Adding a test runtime does not require editing a repository-wide asset list.

The QEMU build entry point stages the QEMU executable, Linux kernel, and Guest root filesystem under its test suite. These files are not profile-declared Exodus runtimes and are not included in the binary Release. Their pinned revisions, build procedure, and runtime inputs are documented in the [QEMU Linux test environment](../tests/integration/qemu/README.md).

Platform build scripts pin their validated upstream revisions. They reject uncommitted tracked changes before fetching and checking out an external workspace. See the Zephyr, NuttX, and QEMU test README files for the authoritative revision values.

Create a distributable ZIP from the same inventory with:

```sh
python scripts/create_binary_release.py \
  --output /tmp/bsworld-prebuilt-vX.Y.Z.zip \
  --nuttx-dir /path/to/nuttx \
  --nuttx-apps-dir /path/to/nuttx-apps \
  --zephyr-workspace /path/to/zephyrproject \
  --bsim-out-dir /tmp/bsworld/build/babblesim/bsim
```

`create_binary_release.py` uses the same discovered runtime assets as the builder. It validates every launcher, rejects undeclared launchers and nested archives, preserves repository-relative paths and Exodus symbolic links, and writes a manifest containing each launcher and the profile source that referenced it, together with checksums, licenses, and source revisions. A `.zip` output creates a standalone package; an output without that suffix creates the same package as a directory.

The Python package version is derived from the repository tag by [setuptools-scm](https://setuptools-scm.readthedocs.io/), making the tag the single source of version information. Before building a tagged release, normalize and compare the tag with the installed `bsworld` package version. In GitHub Actions, use `GITHUB_REF_NAME` for the tag and check out the full Git history and tags so version discovery can succeed. Stop the release build if the tag is missing or the versions do not match.

For a GitHub release, pass the prepared source workspace paths through the same arguments. After successful tests, use `create_binary_release.py` with `--output dist/bsworld-prebuilt-<tag>.zip` to create a single ZIP, then attach it to the matching GitHub Release. The release is installed with `scripts/install_binary_release.py`; pytest is not involved in installation. A GitHub Actions workflow can supply `NUTTX_DIR`, `NUTTX_APPS_DIR`, `ZEPHYR_WORKSPACE`, and `BSIM_OUT_DIR` as environment variables and pass them to the build and packaging scripts explicitly.

## Coverage

Branch coverage is provided by [coverage.py](https://coverage.readthedocs.io/) and enabled via `[tool.coverage.run]` in `pyproject.toml`.

```sh
# Unit-only coverage, fast and no firmware/BabbleSim required
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
python -m coverage run -m pytest \
  -p pytest_asyncio.plugin -p bsworld.plugin tests/unit
python -m coverage report

# Manual runtime dependency setup, then simulation without coverage instrumentation
export BSIM_OUT_PATH=/tmp/bsworld/build/babblesim/bsim
export BSIM_COMPONENTS_PATH=$PWD/components/babblesim/components
export BSIM_BASE_PATH=$BSIM_COMPONENTS_PATH
export BSIM_BUILD_FAIL_ASAP=1
make -C components/babblesim everything
pytest tests/integration/ -n auto
```

The unit coverage command starts coverage before pytest imports any project module, disables unrelated third-party plugin autoload, and then explicitly loads the asyncio and BSWorld plugins required by the test suite. The configured report covers the `bsworld` package, including its runtime scheduler.
