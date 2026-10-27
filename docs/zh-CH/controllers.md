# 虚拟 Controller

[English](../controllers.md) | 简体中文

BSWorld 测试中，每个蓝牙 Host 都通过 Unix socket 上的标准 H4 HCI 连接自己专属的虚拟 Controller。Controller 运行 Link Layer，经由共享的 BabbleSim PHY 收发报文，因此不同 Host 的 Controller 能通过模拟射频互相通信。

BSWorld 提供两种实现：

| | `ZephyrController` | `BSController` |
|---|---|---|
| 实现 | 为 `nrf52_bsim` 编译的 Zephyr 蓝牙 Controller（[bt_virt_controller](../../components/bt_virt_controller/README.zh-CN.md)） | Python Controller（[bscontroller](../../components/bscontroller/README.zh-CN.md)） |
| 运行方式 | 原生仿真进程，每个 Controller 一个进程 | pytest 进程内的 worker 线程 |
| 依赖 | `BSWORLD_BT_VIRT_CONTROLLER_BIN`（Docker 镜像已内置） | 安装 BSWorld 即可，无其他依赖 |
| 配置 | 由 Zephyr 编译配置决定 | 可按 Controller 分别设置缓冲、列表大小、上限、版本（见[下文](#配置-bscontroller)） |
| 默认 | 是 | 按测试或按 Controller 选择 |

两种实现都会为每个 Controller 生成一份 HCI 抓包（`hciN.snoop`），也都会记录到共享的射频跟踪文件（`ellisys.bttrp`）中。参见[日志、跟踪文件与抓包](artifacts.md)。

## 在测试中添加 Controller

`topo.add_controller()` 返回一个 Controller。在 `topo.start()` 之后，把 Host 连接到它的 `hci_sock`：

```python
from bsworld.devices import BSController

zephyr_ctl = topo.add_controller(public_address="F0:F1:F2:F3:F4:02")
python_ctl = topo.add_controller(
    controller_type=BSController,
    public_address="F0:F1:F2:F3:F4:01",
)
await topo.start()
# 将 Host 分别连接到 zephyr_ctl.hci_sock 和 python_ctl.hci_sock。
```

| 参数 | 含义 |
|---|---|
| `controller_type` | `ZephyrController`（默认）或 `BSController`，同一拓扑可以混用两种。 |
| `public_address` | 公共设备地址，格式为 `AA:BB:CC:DD:EE:FF`。省略时，`BSController` 根据 Controller 编号生成互不相同的地址，`ZephyrController` 保持其编译配置中的地址。 |
| `log_subdir` | 该 Controller 的 `hciN.snoop` 存放位置，相对于测试日志目录。 |
| `config` | 仅限 `BSController`：包含 Controller 自定义参数的 `ControllerConfig`，见[配置 BSController](#配置-bscontroller)。 |
| `max_step_us` | 仅限 `BSController`：worker 空闲时单步推进的最长仿真时间。 |

## 用两种 Controller 运行同一场景

覆盖 `bsworld_default_controller_type` fixture 可设置 `topo` fixture 的默认 `controller_type`，显式传入的 `controller_type` 仍然优先：

```python
import pytest
from bsworld.devices import BSController, ZephyrController


@pytest.fixture(params=[ZephyrController, BSController], ids=["zephyr", "bscontroller"])
def bsworld_default_controller_type(request):
    return request.param
```

用参数 ID 选择其中一种实现：

```sh
pytest tests/integration -n auto -k '[zephyr]'
pytest tests/integration -n auto -k '[bscontroller]'
```

## 配置 BSController

通过 `config=` 传入一个 `ControllerConfig`。字段、默认值和取值范围见 [BSController 配置说明](../../components/bscontroller/README.zh-CN.md#配置)。

```python
from bscontroller import ControllerConfig
from bsworld.devices import BSController

central = topo.add_controller(
    controller_type=BSController,
    config=ControllerConfig(max_connections=1),
)
peripheral = topo.add_controller(
    controller_type=BSController,
    config=ControllerConfig(advertising_set_count=2, acl_packet_count=16),
)
```

## 使用 Zephyr Controller

`ZephyrController` 会为每个 Controller 启动一次 `$BSWORLD_BT_VIRT_CONTROLLER_BIN`。Docker 镜像已包含该程序，编译方法见 [bt_virt_controller 指南](../../components/bt_virt_controller/README.zh-CN.md)。它的输出写在测试日志目录下的 `bt_virt_controller/bt_virt_controller_hciN.log`。
