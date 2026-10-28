# bt_virt_controller

[English](README.md) | [简体中文](README.zh-CN.md)

`bt_virt_controller` is the BSWorld Virtual Controller: an out-of-tree Zephyr Application for [nrf52_bsim](https://docs.zephyrproject.org/latest/boards/native/nrf_bsim/doc/nrf52_bsim.html) running the Zephyr Bluetooth Controller, with H4 HCI over a Unix socket. The executable is selected with `BSWORLD_BT_VIRT_CONTROLLER_BIN`.

## Runtime Contract

BSWorld starts one Virtual Controller per HCI socket:

```text
"$BSWORLD_BT_VIRT_CONTROLLER_BIN" \
  -s=<sim_id> \
  -d=<device_id> \
  -RealEncryption=1 \
  [-hci-poll-interval=<microseconds>] \
  -hci-socket=<hci_socket_path> \
  [-bd-addr=<AA:BB:CC:DD:EE:FF>] \
  [-btsnoop-file=<btsnoop_file_path>]
```

- `-s` and `-d`: BabbleSim simulation ID and device number.
- `-hci-poll-interval`: HCI socket poll interval, also used as the PHY maximum resynchronization offset. Default 1,000 µs.
- `-hci-socket`: H4 HCI socket.
- `-bd-addr`: Controller public address.
- `-btsnoop-file`: BTSnoop capture file.

## Build

The [Docker test image](../../docker/README.md#use-a-published-image) already includes the Controller. For native Linux builds, build BabbleSim using the [repository instructions](../../README.md#build-and-test) and prepare the [Zephyr workspace](../../tests/integration/zephyr/shell/README.md#prepare-the-zephyr-workspace), then:

```sh
source "$ZEPHYR_WORKSPACE/.venv/bin/activate"
cd "$ZEPHYR_WORKSPACE"
west build -p always -b nrf52_bsim \
  -d "$ZEPHYR_WORKSPACE/build/bsworld_bt_virt_controller" \
  "$BSWORLD_ROOT/components/bt_virt_controller"
export BSWORLD_BT_VIRT_CONTROLLER_BIN="$ZEPHYR_WORKSPACE/build/bsworld_bt_virt_controller/zephyr/zephyr.exe"
```

## License and Dependencies

The BSWorld source in this directory is owned by Xiaomi Corporation and licensed under Apache License 2.0. Zephyr and BabbleSim retain their own licenses; see [Third-Party Notices](../../THIRD_PARTY_NOTICES.md).
