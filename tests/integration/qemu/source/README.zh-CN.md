# QEMU Linux Guest 的 Buildroot 配置

[English](README.md) | [中文](README.zh-CN.md)

当前目录是共享 QEMU Linux Guest 使用的标准 Buildroot external tree。`configs/bsworld_qemu_linux_defconfig` 选择 AArch64 系统、Linux kernel、BlueZ 工具、Apache NimBLE 和 TrouBLE；`board/linux/linux.fragment` 启用三套 Host 协议栈共用的 Bluetooth HCI UART 与 PCI serial 驱动。自定义 package 会下载固定的 NimBLE 与 TrouBLE 上游提交，并为 Guest 构建未经修改的 Linux 示例。

Buildroot 自动下载 Bootlin 的预编译 AArch64 glibc stable 工具链，包含 C++ 和线程支持。工具链 profile（`2026.08-1`）由上一级 README 中固定的 Buildroot 提交确定。更换工具链时应使用新的输出目录。

使用以下命令加载配置：

```sh
make -C /path/to/buildroot \
  O=/path/to/buildroot-output \
  BR2_EXTERNAL=/path/to/bsworld/tests/integration/qemu/source \
  bsworld_qemu_linux_defconfig
```

完整的环境准备、构建、验证和许可证处理流程见上一级 [QEMU Linux 测试环境](../README.zh-CN.md)。

这些 BSWorld 构建配置使用 Apache License 2.0，不改变 Buildroot、Linux、BlueZ、Apache NimBLE、TrouBLE 或生成的 Guest 镜像所适用的许可证。
