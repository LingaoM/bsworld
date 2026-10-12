# Zephyr Bluetooth Samples

[English](README.md) | [中文](README.zh-CN.md)

These tests run unmodified Zephyr Bluetooth samples as Host-only processes in BSWorld. A shared configuration and devicetree overlay connects each Host to a separate BSWorld Virtual Controller over a Unix socket.

| Test directory | Zephyr samples | Coverage |
|---|---|---|
| `broadcast_observe/` | `broadcaster`, `observer` | Advertising, passive scanning, and targeted three-channel interference with recovery |
| `heart_rate/` | `peripheral_hr`, `central_hr` | Connection, GATT discovery, and notifications |
| `periodic_advertising/` | `periodic_adv`, `periodic_sync` | Periodic advertising synchronization |
| `mesh/` | `mesh`, `mesh_provisioner` | Mesh provisioning and configuration-model control |

Each directory owns its Python test, process profiles, optional build fragment, build entry point, and generated, expanded `prebuilt/` runtimes. No interactive Zephyr shell is used.

## Build

Prepare the Zephyr and BabbleSim dependencies as described in [`common/source/README.md`](common/source/README.md). Build all sample images:

```sh
tests/integration/zephyr/samples/build.sh \
  --zephyr-workspace /path/to/zephyrproject \
  --bsim-out-dir /tmp/bsworld/build/babblesim/bsim
```

To build one test group, run its local entry point with the same arguments:

```sh
tests/integration/zephyr/samples/heart_rate/build.sh \
  --zephyr-workspace /path/to/zephyrproject \
  --bsim-out-dir /tmp/bsworld/build/babblesim/bsim
```

The expanded Exodus runtime trees are written to `prebuilt/<sample>/` in the selected group. They are ignored by Git, and the group profiles execute their launchers directly.

## Run

```sh
pytest tests/integration/zephyr/samples -q --no-ellisys
```
