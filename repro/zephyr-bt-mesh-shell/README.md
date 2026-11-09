# Zephyr Bluetooth Mesh Shell Reproductions

These tests reproduce bugs in the Zephyr Bluetooth Mesh shell
(`subsys/bluetooth/mesh/shell`) and mismatches with its documentation
(`doc/services/connectivity/bluetooth/api/mesh/shell.rst`). They run the
`tests/bluetooth/mesh_shell` application on `nrf52_bsim/native`, with the Host,
the Zephyr Controller and the radio in one image, in BabbleSim through BSWorld.
Each bug test checks the correct behavior, so it fails before the fix and
passes after it.

| Test | Problem | Issue | Fix |
|---|---|---|---|
| Build | `tests/bluetooth/mesh_shell` does not build on `nrf52_bsim` | [#125081](https://github.com/zephyrproject-rtos/zephyr/issues/125081) | [#125085](https://github.com/zephyrproject-rtos/zephyr/pull/125085) |
| Build | The Mesh shell does not build with the Remote Provisioning Client, or with the Distributor and the host C library | [#125082](https://github.com/zephyrproject-rtos/zephyr/issues/125082) | [#125086](https://github.com/zephyrproject-rtos/zephyr/pull/125086) |
| [test_crashes.py](test_crashes.py) | Five commands crash the device | [#125083](https://github.com/zephyrproject-rtos/zephyr/issues/125083) | [#125087](https://github.com/zephyrproject-rtos/zephyr/pull/125087) |
| [test_arguments.py](test_arguments.py) | Eight commands parse or check their arguments wrongly | [#125084](https://github.com/zephyrproject-rtos/zephyr/issues/125084) | [#125088](https://github.com/zephyrproject-rtos/zephyr/pull/125088) |
| [test_minor.py](test_minor.py) | Ignored parse errors, 32-bit BLOB IDs, missing AD type check, decimal-only arguments, help texts | - | [#125089](https://github.com/zephyrproject-rtos/zephyr/pull/125089) |
| [test_doc_examples.py](test_doc_examples.py) | Documented commands that the shell rejects or treats differently | - | [#125090](https://github.com/zephyrproject-rtos/zephyr/pull/125090) |
| [test_flows.py](test_flows.py) | Provisioning, configuration, Health, Proxy, LPN, Heartbeat, RPR, BLOB and DFU between devices | - | - |

`test_doc_examples.py` and `test_flows.py` pass before and after the fixes.
`test_doc_examples.py` runs each documented form next to the form the shell
accepts.

## Prepare

Set up BSWorld and build BabbleSim as in the [BSWorld README](../../README.md#local-linux),
and prepare a Zephyr workspace with the BabbleSim variables exported.

## Build

On Zephyr main, the application does not build for `nrf52_bsim`, which is the
first issue. Apply #125085 and #125086 before building.

The tests use two images. [full.conf](full.conf) enables every Mesh model that
the shell has commands for, including the Firmware Update models, and
`proxy_solicitation.conf` from the application enables the Proxy Client and
Solicitation. The BLOB Transfer Client commands need an image without the
Firmware Update Client, which [blob.conf](blob.conf) removes.
[native-shell.conf](native-shell.conf) and
[native-shell.overlay](native-shell.overlay) put the shell on standard input
and output.

```sh
REPRO="$BSWORLD_ROOT/repro/zephyr-bt-mesh-shell"
CONF="proxy_solicitation.conf;$REPRO/native-shell.conf;$REPRO/full.conf"
cd "$ZEPHYR_BASE"
west build -p always -b nrf52_bsim/native -d build/mesh_shell tests/bluetooth/mesh_shell -- \
  -DEXTRA_CONF_FILE="$CONF" -DEXTRA_DTC_OVERLAY_FILE="$REPRO/native-shell.overlay"
west build -p always -b nrf52_bsim/native -d build/mesh_shell_blob tests/bluetooth/mesh_shell -- \
  -DEXTRA_CONF_FILE="$CONF;$REPRO/blob.conf" -DEXTRA_DTC_OVERLAY_FILE="$REPRO/native-shell.overlay"
export MESH_SHELL_EXE="$ZEPHYR_BASE/build/mesh_shell/zephyr/zephyr.exe"
export MESH_SHELL_BLOB_EXE="$ZEPHYR_BASE/build/mesh_shell_blob/zephyr/zephyr.exe"
```

Tests that need an image whose variable is not set are skipped.

## Run

```sh
cd "$BSWORLD_ROOT"
source .venv/bin/activate
pytest repro/zephyr-bt-mesh-shell -n auto
```

Each test writes the console of every node to
`/tmp/run-<timestamp>/<uid>/log/<test file>/<test>/<label>/<label>.log`. A test
whose node crashes fails with `<label>: crashed after '<command>'`, and
`bsworld.log` in the same directory reports `exited unexpectedly (rc=-11)`.

## Results

Zephyr main 5b375948321 with #125085 and #125086 as the base, and each other
pull request applied on top of it on its own:

| Test | Base | #125087 | #125088 | #125089 | All |
|---|---|---|---|---|---|
| test_crashes.py (5 tests) | fail | pass | fail | fail | pass |
| test_arguments.py (8 tests) | fail | fail | pass | fail | pass |
| test_minor.py (6 tests) | fail | fail | fail | pass | pass |
| test_doc_examples.py (7 tests) | pass | pass | pass | pass | pass |
| test_flows.py (8 tests) | pass | pass | pass | pass | pass |

Without #125085, `west build -b nrf52_bsim/native tests/bluetooth/mesh_shell`
fails in `lll_conn.c`. With #125085 but without #125086, the `full.conf` build
fails in `rpr.c`. With only the `rpr.c` fix of #125086, a build that adds
[dfd.conf](dfd.conf) (the Firmware Distribution Server) fails in `dfd.c`.
