# bt_virt_controller

[English](README.md) | [中文](README.zh-CN.md)

`bt_virt_controller` is Xiaomi's Virtual Controller implementation for BSWorld. It is an out-of-tree Zephyr Application built for [nrf52_bsim](https://docs.zephyrproject.org/latest/boards/native/nrf_bsim/doc/nrf52_bsim.html). It runs the complete HCI interface and Link Layer protocol logic, and participates in radio transmission, reception, and RF interaction through the BabbleSim PHY. The Virtual Controller exposes a bidirectional H4 transport over a Unix socket and an optional, non-blocking BTSnoop capture socket.

This directory owns the Application source, its build entry point, and the generated runtime tree:

```text
components/bt_virt_controller/
    build.sh
    CMakeLists.txt / Kconfig / prj.conf
    src/
    prebuilt/bt_virt_controller/exodus/
```

The `prebuilt/` directory is generated and ignored by Git. pytest directly runs `prebuilt/bt_virt_controller/exodus/bin/bt_virt_controller`.

## Runtime Contract

BSWorld starts one Virtual Controller per HCI socket:

```sh
bt_virt_controller \
  -s=<sim_id> \
  -d=<device_id> \
  [-hci-poll-interval=<microseconds>] \
  -hci-socket=<hci_socket_path> \
  [-bd-addr=<AA:BB:CC:DD:EE:FF>] \
  [-btsnoop-socket=<btsnoop_socket_path>]
```

- `-s` and `-d` identify the BabbleSim simulation and Controller device.
- `-hci-poll-interval` sets the HCI socket poll interval and applies the same value to the PHY maximum resynchronization offset. It defaults to 1,000 microseconds (1 ms).
- `-hci-socket` carries bidirectional H4 HCI frames.
- `-bd-addr` optionally initializes the Controller public address before the Host connects.
- `-btsnoop-socket` enables a best-effort capture channel that never blocks the HCI data path.

## Build

Install [Exodus](https://pypi.org/project/exodus-bundler/) and build BabbleSim first, as described in the repository root [README](../../README.md). Prepare a Zephyr workspace by following the [Zephyr sample build guide](../../tests/integration/zephyr/samples/common/source/README.md).

Then run the component-owned build script from any directory. External paths are explicit arguments:

```sh
/path/to/bsworld/components/bt_virt_controller/build.sh \
  --zephyr-workspace /path/to/zephyrproject \
  --bsim-out-dir /tmp/bsworld/build/babblesim/bsim
```

The script checks out the validated Zephyr revision, updates the west workspace, builds the Virtual Controller, strips the staged executable, and asks Exodus to create the expanded runtime tree:

```text
components/bt_virt_controller/prebuilt/bt_virt_controller/exodus/bin/bt_virt_controller
```

A manual smoke test can run the generated launcher directly:

```sh
components/bt_virt_controller/prebuilt/bt_virt_controller/exodus/bin/bt_virt_controller --help
```

The default artifact uses the open-source Zephyr Bluetooth Controller. An equivalent artifact may be built with [nRF Connect SDK](https://www.nordicsemi.com/Products/Development-software/nRF-Connect-SDK), but its license terms must be reviewed separately before redistribution.

## License and Dependencies

The BSWorld-specific source in this directory is owned by Xiaomi Corporation and licensed under Apache License 2.0. Generated runtime trees also contain Zephyr, BabbleSim, Exodus, and possibly host runtime components governed by their own licenses. See [Third-Party Notices](../../THIRD_PARTY_NOTICES.md).
