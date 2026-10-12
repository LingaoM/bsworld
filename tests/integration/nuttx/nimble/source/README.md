# NuttX NimBLE Image

[English](README.md) | [中文](README.zh-CN.md)

The NimBLE tests use the stock NuttX `sim:nimble` configuration and the stock `examples/nimble_bleprph` and `examples/nimble_blecent` Applications. BSWorld carries no copied NimBLE Application source.

## Build

Run the suite-owned build script from any directory and pass every external workspace path explicitly:

```sh
/path/to/bsworld/tests/integration/nuttx/nimble/build.sh \
  --nuttx-dir /path/to/nuttx \
  --nuttx-apps-dir /path/to/nuttx-apps \
  --bsim-out-dir /tmp/bsworld/build/babblesim/bsim
```

The script enables `CONFIG_SIM_BSIM_TIME`, the peripheral, central, and observer roles, together with the `nimble_bleprph` and `nimble_blecent` examples. It produces:

```text
tests/integration/nuttx/nimble/prebuilt/nuttx/exodus/bin/nuttx
```

This path is a launcher in an expanded Exodus runtime tree.

Build all NuttX suites with [`../../build.sh`](../../build.sh), or build every BSWorld binary with `scripts/build_all.py`.
