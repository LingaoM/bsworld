# bt_virt_controller

[English](README.md) | [中文](README.zh-CN.md)

`bt_virt_controller` 是 Xiaomi 为 BSWorld 开发的虚拟 Controller 实现。它的源代码独立于 Zephyr 源码树维护，并面向 [nrf52_bsim](https://docs.zephyrproject.org/latest/boards/native/nrf_bsim/doc/nrf52_bsim.html) 构建。该程序运行完整的 HCI 接口和 Link Layer 协议逻辑，并通过 BabbleSim PHY 参与无线数据收发和 RF 交互。虚拟 Controller 提供基于 Unix socket 的双向 H4 传输通道，以及可选的非阻塞 BTSnoop 抓包 socket。

本目录同时管理业务程序源码、独立构建入口和生成的运行目录：

```text
components/bt_virt_controller/
    build.sh
    CMakeLists.txt / Kconfig / prj.conf
    src/
    prebuilt/bt_virt_controller/exodus/
```

`prebuilt/` 是被 Git 忽略的生成目录。pytest 会直接启动 `prebuilt/bt_virt_controller/exodus/bin/bt_virt_controller`。

## 运行接口

BSWorld 为每个 HCI socket 启动一个虚拟 Controller：

```sh
bt_virt_controller \
  -s=<sim_id> \
  -d=<device_id> \
  [-hci-poll-interval=<microseconds>] \
  -hci-socket=<hci_socket_path> \
  [-bd-addr=<AA:BB:CC:DD:EE:FF>] \
  [-btsnoop-socket=<btsnoop_socket_path>]
```

- `-s` 和 `-d` 分别指定 BabbleSim 仿真标识和 Controller 设备编号。
- `-hci-poll-interval` 设置 HCI socket 轮询周期，并将同一个值应用为 PHY 最大重同步间隔；默认值为 1,000 微秒（1 ms）。
- `-hci-socket` 承载双向 H4 HCI 帧。
- `-bd-addr` 用于在 Host 连接前初始化 Controller 的 public address。
- `-btsnoop-socket` 开启独立抓包通道；即使抓包端处理不及时，也不会阻塞 HCI 数据路径。

## 构建

先按照仓库的中文 [README](../../docs/zh-CH/README.md) 安装 [Exodus](https://pypi.org/project/exodus-bundler/) 并构建 BabbleSim，再参考 [Zephyr 示例程序构建说明](../../tests/integration/zephyr/samples/common/source/README.zh-CN.md)准备 Zephyr 源码工作区。

然后可以从任意目录执行本组件自己的构建脚本。所有外部路径都通过参数显式传入：

```sh
/path/to/bsworld/components/bt_virt_controller/build.sh \
  --zephyr-workspace /path/to/zephyrproject \
  --bsim-out-dir /tmp/bsworld/build/babblesim/bsim
```

脚本会切换到经过验证的 Zephyr 提交，更新 west 工作区，构建 Controller，对待处理的可执行文件执行 strip，再由 Exodus 直接生成展开后的运行目录：

```text
components/bt_virt_controller/prebuilt/bt_virt_controller/exodus/bin/bt_virt_controller
```

可以直接执行生成的 launcher 做基本检查：

```sh
components/bt_virt_controller/prebuilt/bt_virt_controller/exodus/bin/bt_virt_controller --help
```

默认产物使用 Zephyr Project 的开源 Bluetooth Controller。也可以使用 [nRF Connect SDK](https://www.nordicsemi.com/Products/Development-software/nRF-Connect-SDK) 构建等价产物，但对外分发前需要单独检查 NCS 的许可证条款。

## 许可证与依赖

本目录中的 BSWorld 定制源码归 Xiaomi Corporation 所有，使用 Apache License 2.0。生成的运行目录还包含 Zephyr、BabbleSim、Exodus，以及可能的 Host 运行库；这些组件遵循各自的许可证。详见[第三方声明](../../docs/zh-CH/THIRD_PARTY_NOTICES.md)。
