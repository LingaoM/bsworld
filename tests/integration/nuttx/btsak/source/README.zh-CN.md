# NuttX BTSak 构建

[English](README.md) | [中文](README.zh-CN.md)

使用上游 `sim:bthcisock` 配置及其原生 Application。先按 [NuttX 环境说明](../../README.zh-CN.md)准备工作区并编译 BabbleSim。

## 编译

使用官方 [configure.sh / make 流程](https://nuttx.apache.org/docs/latest/quickstart/compiling.html)，并启用测试需要的选项：

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

`SIM_BSIM_TIME` 接入仿真时钟。BTSak 禁用 SMP self-test。

产物为 `$NUTTX_DIR/nuttx`。运行 pytest 时必须保证编译链接的 BabbleSim 动态库位于编译时指定的 `$BSIM_OUT_PATH/lib/`。在 BSWorld Python 环境中运行：

```sh
cd "$BSWORLD_ROOT"
source .venv/bin/activate
pytest tests/integration/nuttx/btsak -q
```
