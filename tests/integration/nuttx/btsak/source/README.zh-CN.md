# NuttX BTSak 构建

[English](README.md) | [简体中文](README.zh-CN.md)

构建上游 `sim:bthcisock` 配置。先按 [NuttX 环境说明](../../README.zh-CN.md)准备工作区。

## 编译

配置：

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

编译：

```sh
make -j"$(nproc)"
export BSWORLD_NUTTX_BTSAK_BIN="$NUTTX_DIR/nuttx"
```

运行测试见[测试 README](../README.zh-CN.md#运行)。
