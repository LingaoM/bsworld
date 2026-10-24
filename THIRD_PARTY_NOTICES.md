# Third-Party Notices

[English](THIRD_PARTY_NOTICES.md) | [简体中文](docs/zh-CH/THIRD_PARTY_NOTICES.md)

Third-party components prepare the Docker build environment and test programs. Native build outputs and artifacts in the Docker test image are selected by environment variables. Third-party components retain their own licenses.

## BabbleSim

- Project: BabbleSim
- Source: https://github.com/BabbleSim
- Website: https://babblesim.github.io/
- Source workspace: `.cache/babblesim/components/`, fetched with repo using `components/babblesim.xml`
- License: Apache License 2.0 unless otherwise stated by an individual BabbleSim component.

BSWorld uses repo to fetch official BabbleSim repositories at the validated revisions recorded in `components/babblesim.xml`. Downloaded sources stay in an untracked workspace and are not patched by this repository.

Each BabbleSim component keeps its own license file under that component's `docs/` directory. Review those files together with this notice when packaging or redistributing BabbleSim build artifacts.

## Apache NuttX

- Project: Apache NuttX
- Source: https://github.com/apache/nuttx
- Usage: external source used to build the NuttX test images documented under `tests/integration/nuttx/`
- Generated runtimes: `BSWORLD_NUTTX_BTSAK_BIN` and `BSWORLD_NUTTX_NIMBLE_BIN`
- License: Apache License 2.0

BSWorld does not vendor Apache NuttX. The NuttX tests document how to build test images from a separate NuttX checkout.

## Apache NimBLE

- Project: Apache Mynewt NimBLE
- Source: https://github.com/apache/mynewt-nimble
- Usage: external Bluetooth Host stack used by the NuttX NimBLE tests and by the upstream Linux example inside the QEMU Guest
- Generated runtimes: `BSWORLD_NUTTX_NIMBLE_BIN` and `BSWORLD_QEMU_ROOTFS`
- License: Apache License 2.0

BSWorld does not vendor Apache NimBLE. The NuttX image obtains it through NuttX apps; the QEMU Buildroot configuration downloads a pinned upstream revision and preserves its `LICENSE` and `NOTICE` files in Buildroot's `legal-info` output.

## TrouBLE

- Project: TrouBLE
- Source: https://github.com/embassy-rs/trouble
- Usage: Rust Bluetooth Host stack used by the Linux Battery Service example inside the QEMU Guest
- Generated runtime: `BSWORLD_QEMU_ROOTFS`
- License: MIT or Apache License 2.0

BSWorld does not vendor TrouBLE. `tests/integration/trouble/source` consumes the unmodified upstream Battery Service applications, and through them the `trouble-host` stack, as a Cargo git dependency pinned to a single upstream revision; Cargo retains the upstream license files in its checkout. Only the native transport and executor in that directory are maintained by BSWorld.

## Bumble

- Project: Bumble
- Source: https://github.com/google/bumble
- Usage: Python Bluetooth Host stack used by `tests/integration/bumble/`;
- License: Apache License 2.0

BSWorld uses the Bumble Host stack through its public Python and HCI transport APIs and does not modify its source code.

## Zephyr Project

- Project: Zephyr Project
- Source: https://github.com/zephyrproject-rtos/zephyr
- Usage: build dependency for the BSWorld Virtual Controller source under `components/bt_virt_controller/` and for the Zephyr sample tests under `tests/integration/zephyr/`
- Generated runtimes: `BSWORLD_BT_VIRT_CONTROLLER_BIN` and `BSWORLD_ZEPHYR_*_BIN`
- License: Apache License 2.0

`components/bt_virt_controller/` is BSWorld source code built as an out-of-tree Zephyr Application. Zephyr sample tests are built from a separate Zephyr workspace.

## QEMU

- Project: QEMU
- Upstream source: https://gitlab.com/qemu-project/qemu
- BSWorld fork: https://github.com/LingaoM/qemu
- Usage: runs the shared Linux Guest used by `tests/integration/qemu/*/`, and synchronizes TCG instruction-counting time with BabbleSim
- Distribution: built from a separate source checkout; not vendored in this repository
- License: GNU General Public License version 2 for QEMU as a whole; individual files may carry compatible licenses

The BSWorld QEMU tests use a modified QEMU fork. Redistributing its executable requires compliance with QEMU's license, including the applicable corresponding-source and notice obligations. The QEMU build procedure and validated source revision are documented under `tests/integration/qemu/`.

## Buildroot

- Project: Buildroot
- Source: https://gitlab.com/buildroot.org/buildroot
- Usage: downloads a prebuilt cross toolchain and uses it to build the Linux kernel, initramfs, BlueZ, Apache NimBLE, and supporting Guest packages used by `tests/integration/qemu/`
- Repository copies: only BSWorld-owned Buildroot external configuration files under `tests/integration/qemu/source/`; Buildroot source is not vendored
- License: GNU General Public License version 2 or later for Buildroot, with exceptions and per-file licenses described by the upstream `COPYING` file

Buildroot is a build system; its license does not replace the licenses of software assembled into the generated root filesystem. Run Buildroot's `legal-info` target against the exact release configuration and review the resulting package licenses, notices, and corresponding-source material before distributing a Guest image.

## BlueZ

- Project: BlueZ
- Source: https://git.kernel.org/pub/scm/bluetooth/bluez.git
- Usage: Linux Bluetooth Host stack, daemon, and command-line tools inside the QEMU Guest image
- Distribution: downloaded and built by Buildroot; not vendored in this repository
- License: GNU General Public License version 2 or later and GNU Lesser General Public License version 2.1 or later, depending on the component

The Guest also contains D-Bus, BusyBox, glibc, and transitive dependencies selected by Buildroot. Their exact versions and licenses must be taken from the `legal-info` output generated for the distributed image.
