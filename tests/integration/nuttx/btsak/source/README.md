# NuttX BTSak Build

[English](README.md) | [简体中文](README.zh-CN.md)

Use the upstream `sim:bthcisock` configuration and stock Applications. Prepare the workspaces and BabbleSim from the [NuttX environment guide](../../README.md).

## Build

Use the official [configure.sh / make workflow](https://nuttx.apache.org/docs/latest/quickstart/compiling.html), enabling the options required by these tests:

```sh
# Keep BSIM_OUT_PATH and BSIM_COMPONENTS_PATH from the BabbleSim build.
source "$BSWORLD_ROOT/.venv/bin/activate"
cd "$NUTTX_DIR"
# Only needed when this tree was previously configured.
if [ -f .config ]; then make distclean; fi
./tools/configure.sh -l -a "$(realpath --relative-to="$NUTTX_DIR" "$NUTTX_APPS_DIR")" sim:bthcisock
kconfig-tweak --file .config -e SIM_BSIM_TIME -d BLUETOOTH_SMP_SELFTEST
make olddefconfig
make -j"$(nproc)"
export BSWORLD_NUTTX_BTSAK_BIN="$NUTTX_DIR/nuttx"
```

`SIM_BSIM_TIME` joins the simulation clock. BTSak disables the SMP self-test.

The output is `$NUTTX_DIR/nuttx`, exported as `BSWORLD_NUTTX_BTSAK_BIN`. Keep its linked BabbleSim shared libraries available at the build-time `$BSIM_OUT_PATH/lib/` path. Run the tests from the [BTSak test README](../README.md#run).
