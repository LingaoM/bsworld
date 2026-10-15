# 第三方声明

[English](../../THIRD_PARTY_NOTICES.md) | [中文](THIRD_PARTY_NOTICES.md)

本仓库引用的第三方组件用于准备 Docker 编译环境及构建测试程序。本机构建产物及 Docker 测试镜像中的产物通过环境变量指定；第三方组件仍遵循各自的许可证。

## BabbleSim

- 项目：BabbleSim
- 源码：https://github.com/BabbleSim
- 网站：https://babblesim.github.io/
- 仓库内位置：`components/babblesim/` 下的 Git submodule
- 许可证：Apache License 2.0；个别 BabbleSim 组件另有声明时，以组件自己的许可证为准

BSWorld 通过 Git submodule 引用 BabbleSim 官方仓库，不会修改 `components/babblesim/` 中检出的上游源码。

每个 BabbleSim 组件都在自己的 `docs/` 目录中保留许可证文件。打包或分发由这些 submodule 构建的产物时，需要同时检查相应许可证文件和本文档。

## Apache NuttX

- 项目：Apache NuttX
- 源码：https://github.com/apache/nuttx
- 用途：构建 `tests/integration/nuttx/` 使用的测试镜像
- 生成的程序：`BSWORLD_NUTTX_BTSAK_BIN` 和 `BSWORLD_NUTTX_NIMBLE_BIN`
- 许可证：Apache License 2.0

BSWorld 不直接包含 Apache NuttX 源码。NuttX 测试文档说明了如何使用独立的 NuttX 源码工作区构建测试镜像。

## Apache NimBLE

- 项目：Apache Mynewt NimBLE
- 源码：https://github.com/apache/mynewt-nimble
- 用途：用于 NuttX NimBLE 测试，以及 QEMU Guest 中的上游 Linux 示例测试
- 生成的程序：`BSWORLD_NUTTX_NIMBLE_BIN` 和 `BSWORLD_QEMU_ROOTFS`
- 许可证：Apache License 2.0

BSWorld 不直接包含 Apache NimBLE 源码。NuttX 镜像通过 NuttX apps 引入 NimBLE；QEMU 的 Buildroot 配置下载固定的上游提交，并在 Buildroot `legal-info` 输出中保留其 `LICENSE` 和 `NOTICE` 文件。

## TrouBLE

- 项目：TrouBLE
- 源码：https://github.com/embassy-rs/trouble
- 用途：QEMU Guest 中 Linux Battery Service 示例使用的 Rust Bluetooth Host 协议栈
- 生成的运行文件：`BSWORLD_QEMU_ROOTFS`
- 许可证：MIT 或 Apache License 2.0

BSWorld 不直接包含 TrouBLE 源码。QEMU 的 Buildroot 配置下载固定的上游提交，交叉编译未经修改的 Linux 示例，并在 Buildroot `legal-info` 输出中保留其许可证文件。

## Bumble

- 项目：Bumble
- 源码：https://github.com/google/bumble
- 用途：作为 `tests/integration/bumble/` 使用的 Python Bluetooth Host 协议栈
- 分发方式：通过 PyPI 安装为默认依赖，不复制到源码仓库中
- 许可证：Apache License 2.0

BSWorld 只使用 Bumble 对外提供的 Python 和 HCI transport 接口，不修改其源码。

## Zephyr Project

- 项目：Zephyr Project
- 源码：https://github.com/zephyrproject-rtos/zephyr
- 用途：构建 `components/bt_virt_controller/` 中的 BSWorld 虚拟 Controller，以及 `tests/integration/zephyr/` 中的 Zephyr 示例测试
- 生成的程序：`BSWORLD_BT_VIRT_CONTROLLER_BIN` 和 `BSWORLD_ZEPHYR_*_BIN`
- 许可证：Apache License 2.0

`components/bt_virt_controller/` 是 BSWorld 自行维护的源码，独立于 Zephyr 源码树维护，并基于 Zephyr 构建。Zephyr 示例测试则使用独立的 Zephyr 源码工作区构建。

## QEMU

- 项目：QEMU
- 上游源码：https://gitlab.com/qemu-project/qemu
- BSWorld fork：https://github.com/LingaoM/qemu
- 用途：运行 `tests/integration/qemu/*/`，并将 TCG 指令计数时间接入 BabbleSim
- 分发方式：从独立源码工作区构建，不复制到本仓库
- 许可证：QEMU 整体使用 GNU General Public License version 2；个别文件可能使用兼容许可证

BSWorld QEMU 测试使用包含修改的 QEMU fork。对外分发其可执行程序时，需要遵守 QEMU 许可证中适用的对应源码和声明义务。QEMU 构建方式及经过验证的源码提交见 `tests/integration/qemu/`。

## Buildroot

- 项目：Buildroot
- 源码：https://gitlab.com/buildroot.org/buildroot
- 用途：下载预编译交叉工具链，并用它构建 `tests/integration/qemu/` 使用的 Linux kernel、initramfs、BlueZ、Apache NimBLE、TrouBLE 和 Guest 配套软件
- 仓库内位置：仅在 `tests/integration/qemu/source/` 保存 BSWorld 自行维护的 Buildroot external 配置，不包含 Buildroot 源码
- 许可证：Buildroot 使用 GNU General Public License version 2 or later；例外情况和单个文件的许可证以上游 `COPYING` 为准

Buildroot 是构建系统，其许可证不能替代根文件系统中各软件自身的许可证。分发 Guest 镜像前，需要针对实际发布配置执行 Buildroot `legal-info` target，并检查生成的软件包许可证、声明和对应源码材料。

## BlueZ

- 项目：BlueZ
- 源码：https://git.kernel.org/pub/scm/bluetooth/bluez.git
- 用途：QEMU Guest 镜像中的 Linux Bluetooth Host 协议栈、daemon 和命令行工具
- 分发方式：由 Buildroot 下载并构建，不复制到本仓库
- 许可证：不同组件分别使用 GNU General Public License version 2 or later 和 GNU Lesser General Public License version 2.1 or later

Guest 中还包含 D-Bus、BusyBox、glibc 及 Buildroot 选择的传递依赖。实际分发版本和许可证应以对应 Guest 镜像生成的 `legal-info` 结果为准。
