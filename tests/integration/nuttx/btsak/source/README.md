# NuttX BTSak Build

[English](README.md) | [简体中文](README.zh-CN.md)

Builds the upstream `sim:bthcisock` configuration. Prepare the workspaces first using the [NuttX environment guide](../../README.md).

## Build

Configure:

```sh
# Keep BSIM_OUT_PATH and BSIM_COMPONENTS_PATH from the BabbleSim build.
source "$BSWORLD_ROOT/.venv/bin/activate"
cd "$NUTTX_DIR"
# Only needed when this tree was previously configured.
if [ -f .config ]; then make distclean; fi
./tools/configure.sh -l -a "$(realpath --relative-to="$NUTTX_DIR" "$NUTTX_APPS_DIR")" sim:bthcisock
kconfig-tweak --file .config -e SIM_BSIM_TIME -d BLUETOOTH_SMP_SELFTEST
make olddefconfig
```

Compile:

```sh
make -j"$(nproc)"
export BSWORLD_NUTTX_BTSAK_BIN="$NUTTX_DIR/nuttx"
```

Run the tests from the [test README](../README.md#run).
