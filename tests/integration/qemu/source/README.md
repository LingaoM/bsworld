# Buildroot Inputs for the QEMU Linux Guest

[English](README.md) | [中文](README.zh-CN.md)

This directory is a standard Buildroot external tree for the shared QEMU Linux Guest. `configs/bsworld_qemu_linux_defconfig` selects the AArch64 system, Linux kernel, BlueZ tools, Apache NimBLE, and TrouBLE. `board/linux/linux.fragment` enables the Bluetooth HCI UART and PCI serial drivers used by all three Host stacks. The custom packages download pinned upstream NimBLE and TrouBLE revisions and build their unmodified Linux examples for the Guest.

Buildroot automatically downloads Bootlin's prebuilt AArch64 glibc stable toolchain with C++ and thread support. The toolchain profile (`2026.08-1`) is fixed by the Buildroot revision documented in the parent README. Use a fresh output directory when changing toolchains.

Load the configuration with:

```sh
make -C /path/to/buildroot \
  O=/path/to/buildroot-output \
  BR2_EXTERNAL=/path/to/bsworld/tests/integration/qemu/source \
  bsworld_qemu_linux_defconfig
```

The complete environment, build, validation, and license procedure is documented in the parent [QEMU Linux Test Environment](../README.md).

These BSWorld build inputs are licensed under Apache License 2.0. They do not change the licenses of Buildroot, Linux, BlueZ, Apache NimBLE, TrouBLE, or the generated Guest image.
