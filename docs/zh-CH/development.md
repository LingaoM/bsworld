# 开发和单元测试

[English](../development.md) | [中文](development.md)

本机开发先按 README 的[本地 Linux 环境搭建](README.md#本地-linux)准备依赖并安装 BSWorld，再执行本文命令。容器中的测试命令见 [Docker 文档](../../docker/README.zh-CN.md#运行测试)。

## 运行单元测试

在仓库根目录运行：

```sh
cd "$BSWORLD_ROOT"
source .venv/bin/activate
pytest tests/unit -q
```

## 单元测试覆盖的核心行为

单元测试重点验证 README 中承诺的以下行为：

- 命令行参数、输出目录、xdist 运行标识共享和 `--no-hci-dump`：`tests/unit/test_plugin.py`
- 环境变量指定产物路径、BabbleSim 程序与动态模型检查，以及原生程序就绪检查：`tests/unit/test_env.py`、`tests/unit/test_artifact_paths.py`、`tests/unit/test_dependency_readiness.py`
- 虚拟 Controller 初始化、业务程序登记、设备编号分配和拓扑生命周期：`tests/unit/test_topology.py`、`tests/unit/test_babblesim_backend.py`
- 与 asyncio 兼容的离散时间、回调和 I/O 执行顺序、时钟协议与 FIFO 日志读取：`tests/unit/test_scheduler.py` 和 `tests/unit/test_runtime.py`
- 虚拟 Controller BTSnoop socket 抓包：`tests/unit/test_hci.py`
- RF 干扰和路径衰减配置：`tests/unit/test_interference.py`、`tests/unit/test_babblesim_backend.py`

业务程序行为、RF 传播本身，以及端到端 Bluetooth LE 示例，由 `tests/integration/*` 下的仿真测试覆盖。

## 单元测试组织

单元测试应该覆盖稳定的对外行为，而不是偶然形成的内部控制流。每个测试尽量只验证一项明确行为，并按子系统分组：

- `tests/unit/test_plugin.py`：pytest 插件参数和测试会话环境。
- `tests/unit/test_topology.py`：测试拓扑编排、通用进程生命周期和 Controller 分配。
- `tests/unit/test_babblesim_backend.py`：BabbleSim 进程参数、设备编号分配、干扰、跟踪文件转换和清理。
- `tests/unit/test_hci.py`：虚拟 Controller BTSnoop socket 抓包。
- `tests/unit/test_scheduler.py`：事件循环时间切换、标准 asyncio 原语和 I/O 执行顺序。
- `tests/unit/test_bsim_clock.py`：FIFO 注册、二进制消息编码、连接与应答超时、不完整读写和断连处理。
- `tests/unit/test_runtime.py`：FIFO 日志采集和完整行匹配。
- `tests/unit/test_interference.py`：RF 配置校验。

`tests/integration/babblesim/test_babblesim_clock.py` 使用真实 PHY 验证 Python 时钟，覆盖资源清理、PHY 断连、无应答超时，以及连接前 PHY 被强杀的情况。该测试需要构建 BabbleSim，但不依赖业务程序或 Controller 镜像。

不要编写仅用于固定私有回退顺序或内部表项顺序的测试。如果某项行为确实重要，测试名称应直接描述它所验证的外部可见约定。

## 静态检查

使用 [Ruff](https://docs.astral.sh/ruff/) 执行 Python 静态检查：

```sh
ruff check src tests
ruff check --fix src tests
```

配置在 `pyproject.toml` 的 `[tool.ruff]` 下。

## 文档

项目文档使用普通 Markdown 编写。英文公共文档放在 `docs/` 下，对应的中文版本统一放在 `docs/zh-CH/` 下。`components/` 和 `tests/` 中面向具体组件的 README 仍与组件放在一起，中文文件使用 `.zh-CN.md` 后缀。

仓库根目录的 README 是文档入口。功能行为变化时，英文和中文页面需要同步更新。

## 扩展 BSWorld

接入大多数新的 Bluetooth LE 业务程序环境时，只需要在对应测试目录中增加辅助函数和测试用例；涉及原生二进制时在 README 中记录官方构建命令和环境变量。Zephyr 和 NuttX 把进程启动约定放在各自的集成测试目录里，因为不同环境使用的启动参数格式并不相同。Bumble 这类 Python 协议栈可以直接运行在 pytest 中，并连接 Controller socket；BlueZ 这类 Linux 协议栈可以运行在 QEMU Guest 中，由 HCI UART 桥接到相同的 socket 接口。每个登记到拓扑中的业务程序都会分配一个独立的虚拟 Controller。

只有新的接入方式改变了框架的执行约定时，才需要修改公共代码：

- **新的进程启动格式**：增加或扩展测试侧适配代码，由它创建带有该平台 BabbleSim 设备标识参数和 HCI socket 参数的 `ProcessInstance`，并在所属集成测试中实际运行这套适配代码。
- **新的 RF 模型封装**：在 `src/bsworld/interference.py` 中增加对外配置类型和参数校验，在 `src/bsworld/backends/babblesim.py` 中转换为 BabbleSim 参数，并分别测试非法输入和最终生成的命令。

平台专用的进程配置、源码配置和构建说明应留在对应测试目录。只有被多个业务程序环境共同使用，或者属于 BSWorld 公共运行模型的能力，才放入框架源码。

## 测试覆盖率

分支覆盖率由 [coverage.py](https://coverage.readthedocs.io/) 统计，并在 `pyproject.toml` 的 `[tool.coverage.run]` 中启用。

```sh
# 只统计单元测试覆盖率，速度快，不需要固件或 BabbleSim
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
python -m coverage run -m pytest \
  -p pytest_asyncio.plugin -p bsworld.plugin tests/unit
python -m coverage report

# 手动准备运行依赖；仿真测试不插入覆盖率探针
pytest tests/integration/ -n auto
```

这组命令会先启动覆盖率记录，再由 pytest 导入项目代码；同时关闭无关的第三方插件自动加载，只显式启用测试所需的 asyncio 和 BSWorld 插件。最终报告会统计整个 `bsworld` 包，包括 runtime 调度器。
