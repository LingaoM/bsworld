# Zephyr Bluetooth Shell Tests

[English](README.md) | [简体中文](README.zh-CN.md)

These tests build two Host-only Zephyr shell executables: one for Bluetooth/GATT and one for Mesh. Each executable runs as multiple independent processes. Every process has its own Virtual Controller, HCI socket, address, and simulation device identity. Commands in pytest select its role and operations.

The firmware reuses Zephyr's existing application entry points and shell commands. BSWorld maintains the shared configuration, Mesh additions, and HCI overlay in [source/](source/). Both consoles use a native PTY UART mapped to process stdin/stdout, while HCI uses a separate Unix socket.

| Roles | Upstream entry point | Executable variable |
|---|---|---|
| Advertising, scanning, connections, GATT, periodic advertising | `tests/bluetooth/shell` | `BSWORLD_ZEPHYR_SHELL_BIN` |
| Mesh provisioning and configuration | `tests/bluetooth/mesh_shell` | `BSWORLD_ZEPHYR_MESH_SHELL_BIN` |

The [Docker runtime image](../../../../docker/README.md#select-a-suite) packages these as `/opt/firmware/zephyr/shell` and `/opt/firmware/zephyr/mesh_shell` and sets both variables. Run this suite with `pytest tests/integration/zephyr/shell -n 2`. The steps below prepare native Linux builds.

## Prepare the Zephyr Workspace

Prepare BSWorld using the repository README's [local Linux setup](../../../../README.md#local-linux). Install Zephyr's dependencies from its [Getting Started Guide](https://docs.zephyrproject.org/latest/develop/getting_started/index.html), then prepare a workspace at the revision pinned by the Dockerfile:

```sh
export ZEPHYR_WORKSPACE="$HOME/zephyrproject"
mkdir -p "$ZEPHYR_WORKSPACE"

python3.12 -m venv "$ZEPHYR_WORKSPACE/.venv"
source "$ZEPHYR_WORKSPACE/.venv/bin/activate"
python -m pip install west

git init "$ZEPHYR_WORKSPACE/zephyr"
git -C "$ZEPHYR_WORKSPACE/zephyr" remote add origin https://github.com/zephyrproject-rtos/zephyr
git -C "$ZEPHYR_WORKSPACE/zephyr" fetch --depth=1 origin a915b2f12675b48b16d56653ea145dcd8f20cbbf
git -C "$ZEPHYR_WORKSPACE/zephyr" checkout --detach FETCH_HEAD

west init -l "$ZEPHYR_WORKSPACE/zephyr"
cd "$ZEPHYR_WORKSPACE"

west update
west packages pip --install
west zephyr-export

cd zephyr
west sdk install --gnu-toolchains x86_64-zephyr-elf
```

Build BabbleSim using the [repository instructions](../../../../README.md#build-and-test) and retain `BSWORLD_ROOT`, `BSIM_OUT_PATH`, and `BSIM_COMPONENTS_PATH`. Build the [Zephyr Virtual Controller](../../../../components/bt_virt_controller/README.md) when selecting that Controller, and retain `BSWORLD_BT_VIRT_CONTROLLER_BIN`.

## Build and Run

Build both upstream entry points with the configuration in this directory:

```sh
source "$ZEPHYR_WORKSPACE/.venv/bin/activate"
cd "$ZEPHYR_WORKSPACE"

west build -p always -b nrf52_bsim \
  -d "$ZEPHYR_WORKSPACE/build/bsworld_zephyr_shell" \
  "$ZEPHYR_WORKSPACE/zephyr/tests/bluetooth/shell" \
  -- -DCONF_FILE="$BSWORLD_ROOT/tests/integration/zephyr/shell/source/prj.conf" \
  -DDTC_OVERLAY_FILE="$ZEPHYR_WORKSPACE/zephyr/tests/bluetooth/shell/xterm-native-shell.overlay;$BSWORLD_ROOT/tests/integration/zephyr/shell/source/bsim_host_only.overlay"
export BSWORLD_ZEPHYR_SHELL_BIN="$ZEPHYR_WORKSPACE/build/bsworld_zephyr_shell/zephyr/zephyr.exe"

west build -p always -b nrf52_bsim \
  -d "$ZEPHYR_WORKSPACE/build/bsworld_zephyr_mesh_shell" \
  "$ZEPHYR_WORKSPACE/zephyr/tests/bluetooth/mesh_shell" \
  -- -DCONF_FILE="$BSWORLD_ROOT/tests/integration/zephyr/shell/source/prj.conf" \
  -DEXTRA_CONF_FILE="$BSWORLD_ROOT/tests/integration/zephyr/shell/source/mesh.conf" \
  -DDTC_OVERLAY_FILE="$ZEPHYR_WORKSPACE/zephyr/tests/bluetooth/shell/xterm-native-shell.overlay;$BSWORLD_ROOT/tests/integration/zephyr/shell/source/bsim_host_only.overlay"
export BSWORLD_ZEPHYR_MESH_SHELL_BIN="$ZEPHYR_WORKSPACE/build/bsworld_zephyr_mesh_shell/zephyr/zephyr.exe"
```

Switch back to the BSWorld environment in the same terminal, retaining those exports:

```sh
cd "$BSWORLD_ROOT"
source .venv/bin/activate
pytest tests/integration/zephyr/shell -n 2 -q
```

Controller selection follows the repository's [test parametrization](../../../../README.md#test-controller-variants). Advertising, scanning, connections, GATT, and periodic synchronization share the Bluetooth executable; Mesh roles share the separate Mesh executable.

Mesh group control sets and clears the [Health Attention state](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/MshPRT_v1.1/out/en/index-en.html#UUID-3d039b14-437c-82de-8589-cdb675aceb85) on two subscribed nodes, with a third unsubscribed node verifying isolation.

## Scenario Commands

Add scenarios in [test_scenarios.py](test_scenarios.py). Register processes with `add_zephyr_shell()`, start the topology, then call `initialize_shell()` before issuing commands:

```python
from tests.integration.zephyr.shell.devices import add_zephyr_shell, initialize_shell

scanner = add_zephyr_shell(topo, name="scanner", address="C0:FF:EE:41:00:02")
await topo.start()
await initialize_shell(scanner)
await scanner.shell.run("bt scan passive")
await scanner.wait_log("Bluetooth passive scan enabled")
```

The ordinary image initializes with `bt init sync`. For Mesh, pass `mesh=True` to both helpers; initialization waits for the application's startup and runs `mesh init`. Verify command results with `wait_log()`; process output is stored under `zephyr/shell/<name>/`, alongside the shared [HCI and RF artifacts](../../../../docs/artifacts.md).

## License

The BSWorld test code and configuration use Apache License 2.0. Zephyr retains its upstream licenses; see [Third-Party Notices](../../../../THIRD_PARTY_NOTICES.md).
