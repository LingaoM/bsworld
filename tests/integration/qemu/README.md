# QEMU Linux Test Environment

[English](README.md) | [中文](README.zh-CN.md)

BSWorld can run a complete Linux guest as one participant in the BabbleSim time domain. The validated setup uses a single-vCPU AArch64 QEMU `virt` machine and a Buildroot Linux kernel and initramfs containing BlueZ, Apache NimBLE, and TrouBLE. QEMU connects the guest's HCI UART to a BSWorld Virtual Controller through a Host Unix socket, while its instruction-counting clock is synchronized with BabbleSim.

This path is intended for Linux Bluetooth software that should be tested without porting the Application or Host stack to an RTOS. Buildroot is used only to build the guest kernel, root filesystem, and cross toolchain.

## Validated Versions

| Component | Revision or version | Purpose |
|---|---|---|
| BSWorld QEMU fork | `b2d1776bca209773c4a023e4decb785f7dc3cfb4` | Synchronizes TCG `icount` with BabbleSim and orders vCPU execution and Main Loop I/O deterministically |
| Buildroot | `1ad0796f2b40eb8dadc43e95dd1d56708b191375` | Builds the AArch64 Linux guest |
| Linux | `6.18.7` | Guest kernel selected by the maintained defconfig |
| BlueZ | `5.86` | Guest Bluetooth Host stack and command-line tools |
| Apache NimBLE | `1e8ed60276f35a80ed4d4b4f8bb9d9c6fee53845` | Linux Host example inside the Guest |
| TrouBLE | `730198ecf94ee6953163b7485cf902d5f9d45dbd` | Rust Linux Host example inside the Guest |

The Buildroot and package versions are pinned by the validated Buildroot revision and the BSWorld defconfig. Use these revisions when reproducing the current tests; moving either repository independently may change build options, package versions, or runtime behavior.

## Host Requirements

Use a Linux build host. On Ubuntu or Debian, install the tools required by QEMU, Buildroot, and BSWorld:

```sh
sudo apt update
sudo apt install -y \
  bash bc binutils bzip2 build-essential cpio diffutils file findutils \
  gawk gcc g++ git gzip libfdt-dev libglib2.0-dev libncurses-dev \
  libpixman-1-dev make ninja-build patch perl pkg-config python3.12 \
  python3.12-venv python3-pip rsync sed tar unzip wget which zlib1g-dev
```

Do not run Buildroot as `root`. Keep source trees and output directories separate so a configuration can be rebuilt or removed without modifying the upstream checkout.

## Prepare BSWorld and BabbleSim

First complete the root [Quick Start](../../../README.md#quick-start). It installs BSWorld, initializes and builds BabbleSim, and installs the Virtual Controller runtime used by every integration suite. Keep the `BSIM_OUT_PATH` and `BSIM_COMPONENTS_PATH` values from that setup in the current shell.

Set `BSWORLD_ROOT` to the BSWorld checkout used by that setup:

```sh
export BSWORLD_ROOT=/path/to/bsworld
```

## Build QEMU and the Linux Guest

Clone the QEMU fork and official Buildroot repository. The build entry point fetches and checks out the validated revisions listed above:

```sh
git clone https://github.com/LingaoM/qemu.git /path/to/qemu
git clone https://gitlab.com/buildroot.org/buildroot.git /path/to/buildroot
```

Run the platform build entry point from the BSWorld repository:

```sh
cd "$BSWORLD_ROOT"

tests/integration/qemu/build.sh \
  --qemu-dir /path/to/qemu \
  --buildroot-dir /path/to/buildroot \
  --bsim-out-dir "$BSIM_OUT_PATH"
```

Before changing either source checkout, the script rejects uncommitted tracked changes. It then checks out the pinned revisions, configures and builds QEMU, builds the Linux Guest with the maintained Buildroot external tree, and stages the three shared test inputs under `tests/integration/qemu/prebuilt/`. Pass `--jobs N` to control Buildroot parallelism. `--skip-source-update` skips repository fetch and checkout but still requires both workspaces to already be at the validated revisions.

By default, intermediate build output is stored under the external workspaces:

| Output | Default path |
|---|---|
| QEMU build directory | `/path/to/qemu/build/bsworld/` |
| Buildroot output directory | `/path/to/buildroot/output-bsworld-linux/` |
| Test-ready QEMU executable | `tests/integration/qemu/prebuilt/qemu-system-aarch64` |
| Test-ready Linux kernel | `tests/integration/qemu/prebuilt/Image` |
| Test-ready Guest root filesystem | `tests/integration/qemu/prebuilt/rootfs.cpio` |

Use `--qemu-build-dir` or `--buildroot-output-dir` when CI or a local build needs different intermediate output locations. The staged `prebuilt/` directory is ignored by Git and is not part of the BSWorld binary Release.

The build entry point configures QEMU with `--enable-bsim`, passes the BSWorld BabbleSim component tree through `--bsim-components-path`, and forwards `--bsim-out-dir` as `--bsim-out-path`. QEMU derives the static library directory from `<bsim-out-path>/lib`; no separate library-path option is required. The BabbleSim communication libraries are linked into `qemu-system-aarch64`, so the executable does not load `libPhyComv1.so` at runtime.

The maintained Buildroot external tree is located at `tests/integration/qemu/source`. It contains a minimal defconfig, a Linux configuration fragment, and package definitions for NimBLE and TrouBLE; no upstream source patches are required. The first build compiles a complete cross toolchain and installs a prebuilt Rust compiler for the TrouBLE cross-build, so it can take substantially longer than later incremental builds. Buildroot downloads upstream source archives during this step; standard Git and HTTPS access to the public upstream servers is required.

The maintained configuration intentionally produces only the artifacts required by BSWorld:

| Setting | Result |
|---|---|
| AArch64 `virt` target | Matches QEMU `-M virt -cpu cortex-a53` |
| Linux Bluetooth, HCI UART H4, and 8250 PCI serial | Exposes the QEMU HCI channel as guest `/dev/ttyS0` |
| BlueZ CLI and tools | Installs `bluetoothd`, `bluetoothctl`, `btattach`, and `hciconfig`; BlueZ selects D-Bus automatically |
| Apache NimBLE Linux example | Builds `nimble-linux` from a pinned upstream revision and opens `hci0` through HCI User Channel |
| TrouBLE Linux example | Cross-compiles `trouble-ble-bas-peripheral` from a pinned upstream revision and opens `hci0` through HCI User Channel |
| CPIO root filesystem | Produces an initramfs loaded directly into guest memory |
| No EXT2/EXT4 image | Avoids an unused virtual disk image |
| No Buildroot `host-qemu` | Avoids compiling a second QEMU without the BSWorld integration |
| No guest network | The tests use `-nic none`; Bluetooth communication uses the HCI serial channel |

The root filesystem is an initramfs. QEMU expands `rootfs.cpio` into guest memory at every boot, so each test starts from a fresh copy of the same built image and does not depend on a persistent virtual disk.

The Buildroot output can be inspected before running pytest:

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

## Runtime Data Path

At runtime, BSWorld creates the Virtual Controller's Unix socket and starts QEMU with a socket-backed character device. QEMU exposes that character device as the guest's first PCI serial port, `/dev/ttyS0`. The test runs `btattach -B /dev/ttyS0 -P h4 -S 1000000 -N`, which registers `hci0` with the guest Linux Bluetooth subsystem. BlueZ tests control `hci0` through `bluetoothd`, `bluetoothctl`, and the standard kernel API. NimBLE and TrouBLE tests stop `bluetoothd` and claim the same `hci0` through HCI User Channel; TrouBLE first runs `hciconfig hci0 down` because its Linux transport requires the caller to take the device down.

The QEMU command supplies the BabbleSim simulation identity through `-icount`. `bsim-mro=1000` limits each virtual execution interval to 1,000 microseconds, while an earlier timer deadline shortens that interval. At each boundary, QEMU submits the target time to the PHY and holds the vCPU until the PHY acknowledges it. Guest virtual time, timer interrupts, and sleeps therefore follow the same BabbleSim timeline as the Virtual Controller, PHY, pytest, and every other simulated device.

The fork uses a fair execution-order lock shared by the vCPU thread and QEMU Main Loop so Host thread scheduling cannot change the order between Guest execution and Host-side I/O dispatch. This primitive is extracted from QEMU's record/replay lock and preserves the existing record/replay interfaces; BabbleSim synchronization and record/replay are mutually exclusive.

While the vCPU waits for the PHY acknowledgment, it releases the execution-order lock and the Main Loop continues processing Host I/O with blocking polls. After acknowledging the wait, the PHY blocks for this device's next request, so the simulation cannot advance again. QEMU then polls without blocking until no locally queued fd event remains, commits the target virtual time, and allows the vCPU to resume.

## Run the Tests

See the [BlueZ tests](bluez/README.md), [NimBLE Linux test](nimble/README.md), and [TrouBLE Linux test](trouble/README.md) for pytest commands, optional artifact path overrides, validated behavior, and per-test logs.

## Rebuild and Inspect the Configuration

Set the source and output paths used by the build entry point, then inspect the active Buildroot configuration without changing it:

```sh
export BUILDROOT_SOURCE=/path/to/buildroot
export BUILDROOT_OUTPUT=/path/to/buildroot/output-bsworld-linux

make -C "$BUILDROOT_SOURCE" O="$BUILDROOT_OUTPUT" show-info
grep -E 'BR2_(PACKAGE_BLUEZ5|PACKAGE_BSWORLD_NIMBLE|PACKAGE_BSWORLD_TROUBLE|TARGET_ROOTFS|PACKAGE_HOST_QEMU)' \
  "$BUILDROOT_OUTPUT/.config"
```

After changing the maintained defconfig or Linux fragment, remove the Buildroot output directory and rerun the build entry point so the image cannot retain stale package or kernel settings:

```sh
rm -rf "$BUILDROOT_OUTPUT"
tests/integration/qemu/build.sh \
  --qemu-dir /path/to/qemu \
  --buildroot-dir "$BUILDROOT_SOURCE" \
  --bsim-out-dir "$BSIM_OUT_PATH" \
  --skip-source-update
```

## Packaging and License Compliance

The QEMU build entry point stages local test inputs but does not register them as Release-managed runtimes. Tagged binary Releases therefore do not include QEMU, the Linux kernel, or the Guest root filesystem. If any of these files are distributed separately, treat them as third-party binary distributions rather than as Apache-2.0 BSWorld source.

Generate Buildroot's license and corresponding-source report from the exact output directory used for the release:

```sh
make -C "$BUILDROOT_SOURCE" O="$BUILDROOT_OUTPUT" legal-info
```

Review and preserve `$BUILDROOT_OUTPUT/legal-info/` with the release materials. QEMU is distributed under GPL-2.0 and the BSWorld fork contains modifications, so a binary release must also satisfy QEMU's corresponding-source and notice requirements. The guest image contains Linux, BlueZ, Apache NimBLE, TrouBLE, Mbed TLS, D-Bus, BusyBox, glibc, and their dependencies, each under its own terms. Buildroot's `legal-info` output is the starting point for auditing that complete set; it is not a substitute for reviewing the licenses of the actual files being distributed.

The BSWorld defconfig, Linux fragment, test code, and documentation in this repository are licensed under Apache License 2.0. See the repository [Third-Party Notices](../../../THIRD_PARTY_NOTICES.md) for component-level references.
