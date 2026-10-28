# bt_virt_controller

[English](README.md) | [简体中文](README.zh-CN.md)

`bt_virt_controller` 是 BSWorld 的虚拟 Controller：面向 [nrf52_bsim](https://docs.zephyrproject.org/latest/boards/native/nrf_bsim/doc/nrf52_bsim.html) 的 Zephyr 树外 Application，运行 Zephyr Bluetooth Controller，通过 Unix socket 提供 H4 HCI。可执行文件通过 `BSWORLD_BT_VIRT_CONTROLLER_BIN` 指定。

## 运行接口

BSWorld 为每个 HCI socket 启动一个虚拟 Controller：

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

- `-s`、`-d`：BabbleSim 仿真标识和设备编号。
- `-hci-poll-interval`：HCI socket 轮询周期，同时作为 PHY 最大重同步偏移，默认 1000 µs。
- `-hci-socket`：H4 HCI socket。
- `-bd-addr`：Controller 的 public address。
- `-btsnoop-file`：BTSnoop 抓包文件。

## 构建

[Docker 测试镜像](../../docker/README.zh-CN.md#使用已发布镜像)已包含 Controller。本机构建先按[仓库构建说明](../../docs/zh-CH/README.md#构建与测试)构建 BabbleSim，并准备 [Zephyr 工作区](../../tests/integration/zephyr/shell/README.zh-CN.md#准备-zephyr-工作区)，然后执行：

```sh
source "$ZEPHYR_WORKSPACE/.venv/bin/activate"
cd "$ZEPHYR_WORKSPACE"
west build -p always -b nrf52_bsim \
  -d "$ZEPHYR_WORKSPACE/build/bsworld_bt_virt_controller" \
  "$BSWORLD_ROOT/components/bt_virt_controller"
export BSWORLD_BT_VIRT_CONTROLLER_BIN="$ZEPHYR_WORKSPACE/build/bsworld_bt_virt_controller/zephyr/zephyr.exe"
```

## 许可证与依赖

本目录中的 BSWorld 源码归 Xiaomi Corporation 所有，使用 Apache License 2.0。Zephyr 和 BabbleSim 遵循各自的许可证，详见[第三方声明](../../docs/zh-CH/THIRD_PARTY_NOTICES.md)。
