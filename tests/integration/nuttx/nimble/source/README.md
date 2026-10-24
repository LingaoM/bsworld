# NuttX NimBLE Build

[English](README.md) | [简体中文](README.zh-CN.md)

Use the upstream `sim:nimble` configuration and stock Applications. Prepare the workspaces and BabbleSim from the [NuttX environment guide](../../README.md).

## Build

Use the official [configure.sh / make workflow](https://nuttx.apache.org/docs/latest/quickstart/compiling.html), enabling the options required by these tests:

```sh
# Keep BSIM_OUT_PATH and BSIM_COMPONENTS_PATH from the BabbleSim build.
source "$BSWORLD_ROOT/.venv/bin/activate"
cd "$NUTTX_NIMBLE_DIR"
# Only needed when this tree was previously configured.
if [ -f .config ]; then make distclean; fi
./tools/configure.sh -l -a "$(realpath --relative-to="$NUTTX_NIMBLE_DIR" "$NUTTX_NIMBLE_APPS_DIR")" sim:nimble
kconfig-tweak --file .config -e SIM_BSIM_TIME \
  -d NIMBLE_PORTING_EXAMPLE -d EXAMPLES_NIMBLE \
  -e EXAMPLES_NIMBLE_BLEPRPH -e EXAMPLES_NIMBLE_BLECENT \
  -e NIMBLE_ROLE_PERIPHERAL -e NIMBLE_ROLE_CENTRAL -e NIMBLE_ROLE_OBSERVER
make olddefconfig
make -j"$(nproc)"
export BSWORLD_NUTTX_NIMBLE_BIN="$NUTTX_NIMBLE_DIR/nuttx"
```

`SIM_BSIM_TIME` joins the simulation clock. NimBLE enables the bleprph/blecent examples and the peripheral, central, and observer roles.

The output is `$NUTTX_NIMBLE_DIR/nuttx`, exported as `BSWORLD_NUTTX_NIMBLE_BIN`. Keep its linked BabbleSim shared libraries available at the build-time `$BSIM_OUT_PATH/lib/` path. Run the tests from the [NimBLE test README](../README.md#run).
