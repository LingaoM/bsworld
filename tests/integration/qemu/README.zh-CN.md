# QEMU Linux 测试环境

[English](README.md) | [中文](README.zh-CN.md)

BSWorld 可以将完整的 Linux Guest 作为 BabbleSim 时间域中的一个参与者运行。当前验证环境使用单 vCPU 的 AArch64 QEMU `virt` 机器，由 Buildroot 生成 Linux kernel 和 initramfs，并在同一 Guest 镜像中提供 BlueZ、Apache NimBLE 与 TrouBLE Host 协议栈。QEMU 通过 Host Unix socket 将 Guest 的 HCI UART 连接到 BSWorld 虚拟 Controller，同时将基于指令计数的虚拟时钟与 BabbleSim 同步。

该接入方式面向不适合迁移到 RTOS 的 Linux Bluetooth 软件。Buildroot 只负责构建 Guest kernel、根文件系统和交叉工具链。

## 已验证版本

| 组件 | 提交或版本 | 用途 |
|---|---|---|
| BSWorld QEMU fork | `b2d1776bca209773c4a023e4decb785f7dc3cfb4` | 将 TCG `icount` 接入 BabbleSim，并确定性地编排 vCPU 与 Main Loop 的执行顺序 |
| Buildroot | `1ad0796f2b40eb8dadc43e95dd1d56708b191375` | 构建 AArch64 Linux Guest |
| Linux | `6.18.7` | 由仓库内 defconfig 选择的 Guest kernel |
| BlueZ | `5.86` | Guest 内的 Bluetooth Host 协议栈和命令行工具 |
| Apache NimBLE | `1e8ed60276f35a80ed4d4b4f8bb9d9c6fee53845` | Guest 内的 Linux Host 示例 |
| TrouBLE | `730198ecf94ee6953163b7485cf902d5f9d45dbd` | Guest 内的 Rust Linux Host 示例 |

Linux 与 BlueZ 版本由经过验证的 Buildroot 提交和 BSWorld defconfig 共同确定。复现当前测试时应使用表中的提交；单独升级任一外部仓库都可能改变构建选项、软件版本或运行行为。

## 主机依赖

构建主机需要运行 Linux。Ubuntu 或 Debian 可以安装以下 QEMU、Buildroot 和 BSWorld 依赖：

```sh
sudo apt update
sudo apt install -y \
  bash bc binutils bzip2 build-essential cpio diffutils file findutils \
  gawk gcc g++ git gzip libfdt-dev libglib2.0-dev libncurses-dev \
  libpixman-1-dev make ninja-build patch perl pkg-config python3.12 \
  python3-pip rsync sed tar unzip wget zlib1g-dev
```

不要以 `root` 身份运行 Buildroot。源码目录与输出目录应相互独立，便于在不修改上游源码的前提下重新配置、清理或重建产物。

## 准备 BSWorld 与 BabbleSim

先完成仓库根目录 [README 的快速开始](../../../docs/zh-CH/README.md#快速开始)，安装 BSWorld、初始化并构建 BabbleSim，并安装所有集成测试共用的虚拟 Controller 运行文件。后续步骤继续使用其中设置的 `BSIM_OUT_PATH` 和 `BSIM_COMPONENTS_PATH`。

将 `BSWORLD_ROOT` 指向完成上述准备工作的 BSWorld 源码目录：

```sh
export BSWORLD_ROOT=/path/to/bsworld
```

## 构建 QEMU 与 Linux Guest

拉取 QEMU fork 和 Buildroot 官方仓库。构建入口会自动获取并检出前面列出的固定提交：

```sh
git clone https://github.com/LingaoM/qemu.git /path/to/qemu
git clone https://gitlab.com/buildroot.org/buildroot.git /path/to/buildroot
```

在 BSWorld 仓库中执行平台构建入口：

```sh
cd "$BSWORLD_ROOT"

tests/integration/qemu/build.sh \
  --qemu-dir /path/to/qemu \
  --buildroot-dir /path/to/buildroot \
  --bsim-out-dir "$BSIM_OUT_PATH"
```

脚本在切换源码版本前会拒绝包含未提交受版本控制文件的工作区，随后检出固定提交、配置并构建 QEMU、使用仓库内 Buildroot external tree 构建 Linux Guest，最后将测试需要的三个共享文件放入 `tests/integration/qemu/prebuilt/`。可以通过 `--jobs N` 控制 Buildroot 并行任务数。`--skip-source-update` 会跳过仓库 fetch 和 checkout，但两个工作区仍必须处于经过验证的提交。

中间构建结果默认保存在外部源码工作区中：

| 产物 | 默认路径 |
|---|---|
| QEMU 构建目录 | `/path/to/qemu/build/bsworld/` |
| Buildroot 输出目录 | `/path/to/buildroot/output-bsworld-linux/` |
| 测试使用的 QEMU 可执行程序 | `tests/integration/qemu/prebuilt/qemu-system-aarch64` |
| 测试使用的 Linux kernel | `tests/integration/qemu/prebuilt/Image` |
| 测试使用的 Guest 根文件系统 | `tests/integration/qemu/prebuilt/rootfs.cpio` |

CI 或本地构建需要使用其他中间目录时，可以传入 `--qemu-build-dir` 和 `--buildroot-output-dir`。仓库会忽略生成的 `prebuilt/` 目录，该目录也不会进入 BSWorld 二进制 Release。

构建入口使用 `--enable-bsim` 启用 QEMU 的 BabbleSim 支持，通过 `--bsim-components-path` 传入 BSWorld 仓库中的 BabbleSim 组件目录，并将 `--bsim-out-dir` 转交给 `--bsim-out-path`。QEMU 从 `<bsim-out-path>/lib` 推导静态库目录，不需要额外的库路径参数。BabbleSim 通信库会直接链接到 `qemu-system-aarch64` 中，运行时不会加载 `libPhyComv1.so`。

仓库中的 `tests/integration/qemu/source` 是标准 Buildroot external tree，其中维护了裁剪后的 defconfig、Linux 配置片段以及 NimBLE 和 TrouBLE package，不需要修改上游源码。首次构建会编译完整交叉工具链，并安装 TrouBLE 交叉编译所需的预编译 Rust compiler，耗时明显长于后续增量构建。Buildroot 会在此过程中下载上游源码包，因此构建主机需要能够通过标准 Git 和 HTTPS 访问公开的上游服务器。

仓库内配置只生成 BSWorld 实际需要的内容：

| 配置 | 结果 |
|---|---|
| AArch64 `virt` target | 对应 QEMU 的 `-M virt -cpu cortex-a53` |
| Linux Bluetooth、HCI UART H4 与 8250 PCI serial | 将 QEMU HCI 通道呈现为 Guest `/dev/ttyS0` |
| BlueZ CLI 与 tools | 安装 `bluetoothd`、`bluetoothctl`、`btattach` 和 `hciconfig`；BlueZ 自动选择 D-Bus |
| Apache NimBLE Linux 示例 | 从固定上游提交构建 `nimble-linux`，通过 `hci0` 的 HCI User Channel 访问 Controller |
| TrouBLE Linux 示例 | 从固定上游提交交叉编译 `trouble-ble-bas-peripheral`，通过 `hci0` 的 HCI User Channel 访问 Controller |
| CPIO 根文件系统 | 生成启动时直接装入 Guest 内存的 initramfs |
| 不生成 EXT2/EXT4 | 避免构建测试不会使用的虚拟磁盘镜像 |
| 不构建 Buildroot `host-qemu` | 避免额外编译一份不支持 BSWorld 时间同步的 QEMU |
| 不启用 Guest 网络 | 测试使用 `-nic none`，Bluetooth 数据通过 HCI 串口通道传输 |

根文件系统采用 initramfs。QEMU 每次启动都会把 `rootfs.cpio` 重新展开到 Guest 内存，因此每个测试都从同一构建镜像的全新副本开始，不依赖持久化虚拟磁盘。

运行 pytest 前可以检查 Buildroot 产物和 Guest 工具是否完整：

```sh
export BUILDROOT_OUTPUT=/path/to/buildroot/output-bsworld-linux

test -f "$BUILDROOT_OUTPUT/images/Image"
test -f "$BUILDROOT_OUTPUT/images/rootfs.cpio"
test -x "$BUILDROOT_OUTPUT/target/usr/bin/btattach"
test -x "$BUILDROOT_OUTPUT/target/usr/bin/hciconfig"
test -x "$BUILDROOT_OUTPUT/target/usr/bin/bluetoothctl"
test -x "$BUILDROOT_OUTPUT/target/usr/libexec/bluetooth/bluetoothd"
test -x "$BUILDROOT_OUTPUT/target/usr/bin/nimble-linux"
test -x "$BUILDROOT_OUTPUT/target/usr/bin/trouble-ble-bas-peripheral"
test ! -e "$BUILDROOT_OUTPUT/host/bin/qemu-system-aarch64"
```

## 运行时数据路径

运行时，BSWorld 先创建虚拟 Controller 的 Unix socket，再以 socket-backed character device 启动 QEMU。QEMU 将该字符设备映射为 Guest 中的第一个 PCI 串口 `/dev/ttyS0`。测试随后执行 `btattach -B /dev/ttyS0 -P h4 -S 1000000 -N`，把 H4 串口注册为 Linux Bluetooth 子系统中的 `hci0`。BlueZ 测试由 `bluetoothd` 和 `bluetoothctl` 通过标准 Linux Bluetooth kernel 接口控制 `hci0`；NimBLE 和 TrouBLE 测试停止 `bluetoothd`，再通过 HCI User Channel 独占同一个 `hci0`。TrouBLE 的 Linux transport 要求调用方先关闭设备，因此测试还会执行 `hciconfig hci0 down`。

QEMU 启动命令通过 `-icount` 传入 BabbleSim 仿真标识。`bsim-mro=1000` 将每段虚拟执行区间限制在 1000 微秒以内；如果定时器更早到期，则使用更短的区间。到达同步边界后，QEMU 向 PHY 提交目标时间，并保持 vCPU 等待，直到收到 PHY 确认。因此，Guest 虚拟时钟、定时器中断和 sleep 与虚拟 Controller、PHY、pytest 及其他仿真设备沿同一条 BabbleSim 时间轴运行。

为了避免宿主机线程调度改变 Guest 执行与宿主机 I/O 派发的先后关系，QEMU fork 使用一个由 vCPU 线程和 Main Loop 共用的公平执行顺序锁。该机制从 QEMU record/replay 原有的锁中抽取而来，并保留其现有接口；BabbleSim 时间同步与 record/replay 不能同时启用。

vCPU 等待 PHY 确认时会释放执行顺序锁，Main Loop 继续使用阻塞式轮询处理宿主机 I/O。PHY 发出确认后会阻塞等待该设备的下一条请求，因此仿真不会再次向前推进。QEMU 随后改用非阻塞轮询，直到已经到达本机的 fd 事件全部处理完毕，再提交目标虚拟时间并恢复 vCPU 执行。
## 运行测试

pytest 命令、可选的产物路径覆盖方式、已验证场景和日志说明分别见 [BlueZ 测试](bluez/README.zh-CN.md)、[NimBLE Linux 测试](nimble/README.zh-CN.md)与 [TrouBLE Linux 测试](trouble/README.zh-CN.md)。

## 重新构建与检查配置

设置构建入口使用的源码与输出路径后，可以在不修改配置的情况下查看当前 Buildroot 选择：

```sh
export BUILDROOT_SOURCE=/path/to/buildroot
export BUILDROOT_OUTPUT=/path/to/buildroot/output-bsworld-linux

make -C "$BUILDROOT_SOURCE" O="$BUILDROOT_OUTPUT" show-info
grep -E 'BR2_(PACKAGE_BLUEZ5|PACKAGE_BSWORLD_NIMBLE|PACKAGE_BSWORLD_TROUBLE|TARGET_ROOTFS|PACKAGE_HOST_QEMU)' \
  "$BUILDROOT_OUTPUT/.config"
```

修改仓库内 defconfig 或 Linux fragment 后，应删除 Buildroot 输出目录并重新运行构建入口，避免镜像残留旧的软件包或 kernel 配置：

```sh
rm -rf "$BUILDROOT_OUTPUT"
tests/integration/qemu/build.sh \
  --qemu-dir /path/to/qemu \
  --buildroot-dir "$BUILDROOT_SOURCE" \
  --bsim-out-dir "$BSIM_OUT_PATH" \
  --skip-source-update
```

## 打包与许可证合规

QEMU 构建入口只准备本地测试文件，不会把它们登记为 Release 运行程序，因此 tag 对应的二进制 Release 不包含 QEMU、Linux kernel 或 Guest 根文件系统。如果单独分发这些文件，应将其视为第三方二进制发行物，而不是 Apache-2.0 的 BSWorld 源码。

针对实际用于发布的 Buildroot 输出目录生成许可证和对应源码报告：

```sh
make -C "$BUILDROOT_SOURCE" O="$BUILDROOT_OUTPUT" legal-info
```

发布时需要检查并保留 `$BUILDROOT_OUTPUT/legal-info/` 中的材料。QEMU 使用 GPL-2.0，BSWorld fork 又包含源码修改，因此分发 QEMU 二进制时还需要满足对应源码和许可证声明要求。Guest 镜像包含 Linux、BlueZ、Apache NimBLE、TrouBLE、Mbed TLS、D-Bus、BusyBox、glibc 及其依赖，各组件分别遵循自身许可证。Buildroot 的 `legal-info` 是核对完整依赖集合的起点，不能替代对实际分发文件逐项进行许可证审查。

本仓库中的 BSWorld defconfig、Linux fragment、测试代码和文档使用 Apache License 2.0。各外部组件的来源与许可证见仓库[第三方声明](../../../docs/zh-CH/THIRD_PARTY_NOTICES.md)。
