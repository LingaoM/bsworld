# NuttX NimBLE Build

[English](README.md) | [简体中文](README.zh-CN.md)

Builds the upstream `sim:nimble` configuration. Prepare the workspaces first using the [NuttX environment guide](../../README.md).

## Build

Configure:

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
```

Compile:

```sh
make -j"$(nproc)"
export BSWORLD_NUTTX_NIMBLE_BIN="$NUTTX_NIMBLE_DIR/nuttx"
```

Run the tests from the [test README](../README.md#run).
