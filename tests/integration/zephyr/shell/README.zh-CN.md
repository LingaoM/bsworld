# Zephyr 蓝牙 Shell 测试

[English](README.md) | [简体中文](README.zh-CN.md)

本组测试构建两个 Host-only Zephyr shell 可执行文件，分别运行 Bluetooth/GATT 和 Mesh。每个程序都可以启动为多个独立进程；各进程拥有自己的虚拟 Controller、HCI socket、地址和仿真设备标识，由 pytest 中的命令选择角色和操作。

固件复用 Zephyr 现有的业务入口和 shell 命令。BSWorld 在 [source/](source/) 中维护公共配置、Mesh 增量配置与 HCI overlay。两个控制台都使用映射到进程 stdin/stdout 的 native PTY UART，HCI 则使用独立的 Unix socket。

| 角色 | 上游入口 | 可执行文件变量 |
|---|---|---|
| 广播、扫描、连接、GATT、周期广播 | `tests/bluetooth/shell` | `BSWORLD_ZEPHYR_SHELL_BIN` |
| Mesh 配网和配置 | `tests/bluetooth/mesh_shell` | `BSWORLD_ZEPHYR_MESH_SHELL_BIN` |

[Docker 运行镜像](../../../../docker/README.zh-CN.md#选择测试套件)分别将它们打包为 `/opt/firmware/zephyr/shell` 和 `/opt/firmware/zephyr/mesh_shell`，并设置两个变量。运行本组测试使用 `pytest tests/integration/zephyr/shell -n 2`。以下步骤用于本机 Linux 构建。

## 准备 Zephyr 工作区

按照仓库 README 的[本地 Linux 环境搭建](../../../../docs/zh-CH/README.md#本地-linux)准备 BSWorld，参考 Zephyr 的 [Getting Started Guide](https://docs.zephyrproject.org/latest/develop/getting_started/index.html) 安装其依赖，然后使用 Dockerfile 固定的版本准备工作区：

```sh
export ZEPHYR_WORKSPACE="$HOME/zephyrproject"
mkdir -p "$ZEPHYR_WORKSPACE"

python3.12 -m venv "$ZEPHYR_WORKSPACE/.venv"
source "$ZEPHYR_WORKSPACE/.venv/bin/activate"
python -m pip install west

git init "$ZEPHYR_WORKSPACE/zephyr"
git -C "$ZEPHYR_WORKSPACE/zephyr" remote add origin https://github.com/zephyrproject-rtos/zephyr
git -C "$ZEPHYR_WORKSPACE/zephyr" fetch --depth=1 origin a915b2f12675b48b16d56653ea145dcd8f20cbbf
git -C "$ZEPHYR_WORKSPACE/zephyr" checkout --detach FETCH_HEAD

west init -l "$ZEPHYR_WORKSPACE/zephyr"
cd "$ZEPHYR_WORKSPACE"

west update
west packages pip --install
west zephyr-export

cd zephyr
west sdk install --gnu-toolchains x86_64-zephyr-elf
```

按[仓库构建说明](../../../../docs/zh-CH/README.md#构建与测试)构建 BabbleSim，并保留 `BSWORLD_ROOT`、`BSIM_OUT_PATH` 和 `BSIM_COMPONENTS_PATH`。选择 Zephyr Controller 时，还需构建[Zephyr 虚拟 Controller](../../../../components/bt_virt_controller/README.zh-CN.md)，并保留 `BSWORLD_BT_VIRT_CONTROLLER_BIN`。

## 构建与运行

使用本目录的配置构建两个上游入口：

```sh
source "$ZEPHYR_WORKSPACE/.venv/bin/activate"

cd "$ZEPHYR_WORKSPACE"
west build -p always -b nrf52_bsim \
  -d "$ZEPHYR_WORKSPACE/build/bsworld_zephyr_shell" \
  "$ZEPHYR_WORKSPACE/zephyr/tests/bluetooth/shell" \
  -- -DCONF_FILE="$BSWORLD_ROOT/tests/integration/zephyr/shell/source/prj.conf" \
  -DDTC_OVERLAY_FILE="$ZEPHYR_WORKSPACE/zephyr/tests/bluetooth/shell/xterm-native-shell.overlay;$BSWORLD_ROOT/tests/integration/zephyr/shell/source/bsim_host_only.overlay"
export BSWORLD_ZEPHYR_SHELL_BIN="$ZEPHYR_WORKSPACE/build/bsworld_zephyr_shell/zephyr/zephyr.exe"

west build -p always -b nrf52_bsim \
  -d "$ZEPHYR_WORKSPACE/build/bsworld_zephyr_mesh_shell" \
  "$ZEPHYR_WORKSPACE/zephyr/tests/bluetooth/mesh_shell" \
  -- -DCONF_FILE="$BSWORLD_ROOT/tests/integration/zephyr/shell/source/prj.conf" \
  -DEXTRA_CONF_FILE="$BSWORLD_ROOT/tests/integration/zephyr/shell/source/mesh.conf" \
  -DDTC_OVERLAY_FILE="$ZEPHYR_WORKSPACE/zephyr/tests/bluetooth/shell/xterm-native-shell.overlay;$BSWORLD_ROOT/tests/integration/zephyr/shell/source/bsim_host_only.overlay"
export BSWORLD_ZEPHYR_MESH_SHELL_BIN="$ZEPHYR_WORKSPACE/build/bsworld_zephyr_mesh_shell/zephyr/zephyr.exe"
```

在同一终端中切回 BSWorld 环境，保留这些导出的变量：

```sh
cd "$BSWORLD_ROOT"
source .venv/bin/activate
pytest tests/integration/zephyr/shell -n 2 -q
```

Controller 的选择沿用仓库的[测试参数化方式](../../../../docs/zh-CH/README.md#选择测试用的-controller)。广播、扫描、连接、GATT 和周期同步复用普通 Bluetooth 程序，Mesh 角色复用独立的 Mesh 程序。

Mesh 组控设置和清除两个订阅节点的 [Health Attention 状态](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/MshPRT_v1.1/out/en/index-en.html#UUID-3d039b14-437c-82de-8589-cdb675aceb85)，并以第三个未订阅节点验证隔离。

## 场景命令

在 [test_scenarios.py](test_scenarios.py) 中添加场景。通过 `add_zephyr_shell()` 登记进程，启动拓扑后调用 `initialize_shell()`，再发送命令：

```python
from tests.integration.zephyr.shell.devices import add_zephyr_shell, initialize_shell

scanner = add_zephyr_shell(topo, name="scanner", address="C0:FF:EE:41:00:02")
await topo.start()
await initialize_shell(scanner)
await scanner.shell.run("bt scan passive")
await scanner.wait_log("Bluetooth passive scan enabled")
```

普通镜像通过 `bt init sync` 初始化。Mesh 需要在两个辅助函数中都传入 `mesh=True`，初始化会等待程序自身启动后执行 `mesh init`。通过 `wait_log()` 验证命令结果；进程输出保存在 `zephyr/shell/<name>/`，HCI 和 RF 抓包遵循共用的[产物目录结构](../../../../docs/zh-CH/artifacts.md)。

## 许可证

BSWorld 的测试代码和配置使用 Apache License 2.0；Zephyr 保留其上游许可证，见[第三方声明](../../../../docs/zh-CH/THIRD_PARTY_NOTICES.md)。
