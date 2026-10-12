# NuttX Test Environment

[English](README.md) | [中文](README.zh-CN.md)

## Prepare a NuttX Workspace

For a first-time setup, install system dependencies, Kconfig tools, and the target toolchain by following the Apache NuttX official [Installing](https://nuttx.apache.org/docs/latest/quickstart/install.html) guide.

On Ubuntu / Debian, start with the base dependencies recommended by the NuttX documentation:

```sh
sudo apt install -y \
  bison flex gettext texinfo libncurses5-dev libncursesw5-dev xxd \
  git gperf automake libtool pkg-config build-essential genromfs \
  libgmp-dev libmpc-dev libmpfr-dev libisl-dev binutils-dev libelf-dev \
  libexpat1-dev gcc-multilib g++-multilib picocom u-boot-tools util-linux
```

Then install the Kconfig tools. `kconfig-frontends` provides menuconfig frontends and the `kconfig-tweak` command used by the build snippets below; `python3-kconfiglib` provides the Python Kconfig frontend supported by NuttX. BSWorld's build scripts require Python 3.12 or newer:

```sh
sudo apt install -y \
  kconfig-frontends python3-kconfiglib python3.12 python3.12-venv python3-pip
```

Then prepare matching NuttX and apps checkouts. Their paths are passed to the build scripts independently:

```sh
git clone https://github.com/apache/nuttx.git /path/to/nuttx
git clone https://github.com/apache/nuttx-apps.git /path/to/nuttx-apps
```

The validated revisions are:

| Repository | Revision |
|---|---|
| NuttX | `89c4b8ccaf03f1c6d33624d93ef640d8d176a78d` |
| nuttx-apps | `8404450fb89346ed244d1c701e5feb5d19f32271` |

Before compiling, each standalone build entry point fetches the official Apache repositories, checks out these revisions in detached HEAD state, and verifies the resulting commits. This does not depend on where the local checkout's `origin` points. The script stops before checkout if either repository has uncommitted tracked changes.

## BSWorld Dependencies

BSIM-enabled firmware requires the BabbleSim source and build output from the root BSWorld README. The build entry points receive the BabbleSim output path through `--bsim-out-dir` and derive the component source from this repository.

## Build Entry Points

| Suite | Coverage | Build doc |
|---|---|---|
| BTSak | stock NuttX Bluetooth socket scan/advertise commands | [btsak/source/README.md](btsak/source/README.md) |
| NimBLE | stock NuttX NimBLE central/peripheral connection flow | [nimble/source/README.md](nimble/source/README.md) |

Build every NuttX test image from the BSWorld repository root:

```sh
tests/integration/nuttx/build.sh \
  --nuttx-dir /path/to/nuttx \
  --nuttx-apps-dir /path/to/nuttx-apps \
  --bsim-out-dir /tmp/bsworld/build/babblesim/bsim
```

The `btsak/build.sh` and `nimble/build.sh` entry points accept the same arguments and build only their own suite. Every generated image enables `CONFIG_SIM_BSIM_TIME=y` and joins BabbleSim discrete time.
