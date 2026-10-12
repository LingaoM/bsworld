# NuttX BTSak Image

[English](README.md) | [中文](README.zh-CN.md)

The BTSak tests use the stock NuttX `sim:bthcisock` configuration and stock `btsak` Application. BSWorld carries no copied Application source for this suite.

## Build

Run the suite-owned build script from any directory and pass every external workspace path explicitly:

```sh
/path/to/bsworld/tests/integration/nuttx/btsak/build.sh \
  --nuttx-dir /path/to/nuttx \
  --nuttx-apps-dir /path/to/nuttx-apps \
  --bsim-out-dir /tmp/bsworld/build/babblesim/bsim
```

The script configures NuttX with the supplied apps tree, disables `CONFIG_BLUETOOTH_SMP_SELFTEST`, enables `CONFIG_SIM_BSIM_TIME`, and produces:

```text
tests/integration/nuttx/btsak/prebuilt/nuttx/exodus/bin/nuttx
```

This path is a launcher in an expanded Exodus runtime tree.

Build all NuttX suites with [`../../build.sh`](../../build.sh), or build every BSWorld binary with `scripts/build_all.py`.
