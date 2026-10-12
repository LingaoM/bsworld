# 开发和单元测试

[English](../development.md) | [中文](development.md)

开发和测试需要 Python 3.12 或更高版本。先创建项目虚拟环境，并安装 BSWorld：

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

## 单元测试覆盖的核心行为

单元测试重点验证 README 中承诺的以下行为：

- 命令行参数、输出目录、xdist 运行标识共享和 `--no-hci-dump`：`tests/unit/test_plugin.py`
- 共享构建目录 `/tmp/bsworld/build/`、BabbleSim 就绪检查、官方 `make everything` 构建前提，以及预编译运行目录检查：`tests/unit/test_env.py`、`tests/unit/test_dependency_readiness.py`
- 虚拟 Controller 初始化、业务程序登记、设备编号分配和拓扑生命周期：`tests/unit/test_topology.py`、`tests/unit/test_babblesim_backend.py`
- 与 asyncio 兼容的离散时间、回调和 I/O 执行顺序、时钟协议与 FIFO 日志读取：`tests/unit/test_scheduler.py` 和 `tests/unit/test_runtime.py`
- 虚拟 Controller BTSnoop socket 抓包：`tests/unit/test_hci.py`
- RF 干扰和路径衰减配置：`tests/unit/test_interference.py`、`tests/unit/test_babblesim_backend.py`
- 从测试 Profile 自动发现运行程序、生成展开的 Exodus 运行目录、校验并按仓库相对路径安装 Release，以及校验 Release 目录结构：`tests/unit/test_binary_release.py`

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
- `tests/unit/test_binary_release.py`：从测试 Profile 自动发现运行程序、生成展开的 Exodus 运行目录与安装二进制 Release。

`tests/integration/babblesim/test_babblesim_clock.py` 使用真实 PHY 验证 Python 时钟，覆盖资源清理、PHY 断连、无应答超时，以及连接前 PHY 被强杀的情况。该测试需要构建 BabbleSim，但不依赖业务程序或 Controller 镜像。

不要编写仅用于固定私有回退顺序或内部表项顺序的测试。如果某项行为确实重要，测试名称应直接描述它所验证的外部可见约定。

## 静态检查

使用 [Ruff](https://docs.astral.sh/ruff/) 执行 Python 静态检查：

```sh
ruff check scripts src tests
ruff check --fix scripts src tests
```

配置在 `pyproject.toml` 的 `[tool.ruff]` 下。

## 文档

项目文档使用普通 Markdown 编写。英文公共文档放在 `docs/` 下，对应的中文版本统一放在 `docs/zh-CH/` 下。`components/` 和 `tests/` 中面向具体组件的 README 仍与组件放在一起，中文文件使用 `.zh-CN.md` 后缀。

仓库根目录的 README 是文档入口。功能行为变化时，英文和中文页面需要同步更新。

## 扩展 BSWorld

接入大多数新的 Bluetooth LE 业务程序环境时，只需要在对应测试目录中增加辅助函数和测试用例；只有涉及原生二进制时才需要构建脚本。Zephyr 和 NuttX 把进程启动约定放在各自的集成测试目录里，因为不同环境使用的启动参数格式并不相同。Bumble 这类 Python 协议栈可以直接运行在 pytest 中，并连接 Controller socket；BlueZ 这类 Linux 协议栈可以运行在 QEMU Guest 中，由 HCI UART 桥接到相同的 socket 接口。每个登记到拓扑中的业务程序都会分配一个独立的虚拟 Controller。

只有新的接入方式改变了框架的执行约定时，才需要修改公共代码：

- **新的进程启动格式**：增加或扩展测试侧适配代码，由它创建带有该平台 BabbleSim 设备标识参数和 HCI socket 参数的 `ProcessInstance`，并在所属集成测试中实际运行这套适配代码。
- **新的 RF 模型封装**：在 `src/bsworld/interference.py` 中增加对外配置类型和参数校验，在 `src/bsworld/backends/babblesim.py` 中转换为 BabbleSim 参数，并分别测试非法输入和最终生成的命令。

平台专用的进程配置、源码配置和构建说明应留在对应测试目录。只有被多个业务程序环境共同使用，或者属于 BSWorld 公共运行模型的能力，才放入框架源码。

## 构建与打包预编译产物

虚拟 Controller 和各类固件镜像使用已经展开的 [Exodus](https://pypi.org/project/exodus-bundler/) 运行目录。安装 BSWorld 时会同时安装固定版本的 Exodus 及其 Python 3.12 兼容依赖。

每个依赖或测试套件都管理自己的 `build.sh` 和 `prebuilt/` 输出目录。可以单独构建某套测试、构建某个平台的全部测试，也可以从仓库根目录构建所有产物：

```sh
python scripts/build_all.py \
  --nuttx-dir /path/to/nuttx \
  --nuttx-apps-dir /path/to/nuttx-apps \
  --zephyr-workspace /path/to/zephyrproject \
  --bsim-out-dir /tmp/bsworld/build/babblesim/bsim
```

所有外部源码工作区路径都通过命令行参数明确传入。顶层 Python 构建程序按照依赖顺序调用各平台自己的 Shell 入口。`scripts/runtime_assets.py` 会导入 `tests/` 下的 `devices.py`，自动发现其中带有 `name` 和 `path` 属性的受管理配置对象，并加入 BSWorld 自身声明的虚拟 Controller。平台脚本负责配置源码和编译，再由 Exodus 收集可执行程序及其运行依赖，将展开后的目录直接写到对应测试目录；构建过程不会为每个镜像生成中间压缩包。运行测试时既不会重新构建也不会解压固件，而是直接启动 `prebuilt/<名称>/exodus/bin/*`。

需要随 Release 发布的程序，应当至少由测试目录 `devices.py` 中的一个模块级配置对象引用，该对象需要提供 `name` 和 `path`。仓库内位于 `prebuilt/` 下的程序会被自动收集，外部系统程序不会进入 Release；多个配置对象共用同一程序时只打包一次，生成的清单会记录全部引用来源。新增测试运行程序时，只需在对应测试目录中声明配置对象。

QEMU 构建入口会把 QEMU 可执行程序、Linux kernel 和 Guest 根文件系统放在对应测试目录中。这些文件不是由 Profile 声明的 Exodus 运行程序，不会进入二进制 Release。对应的固定版本、构建步骤和运行输入见 [QEMU Linux 测试环境](../../tests/integration/qemu/README.zh-CN.md)。

各平台构建脚本固定使用经过验证的上游提交。拉取源码并切换外部工作区之前，如果发现已跟踪文件存在未提交修改，脚本会立即停止。准确的提交号统一记录在 Zephyr、NuttX 和 QEMU 测试文档中。

使用同一份资产清单生成可分发 ZIP：

```sh
python scripts/create_binary_release.py \
  --output /tmp/bsworld-prebuilt-vX.Y.Z.zip \
  --nuttx-dir /path/to/nuttx \
  --nuttx-apps-dir /path/to/nuttx-apps \
  --zephyr-workspace /path/to/zephyrproject \
  --bsim-out-dir /tmp/bsworld/build/babblesim/bsim
```

`create_binary_release.py` 与构建程序使用同一组自动发现的运行程序。它会校验所有 launcher，拒绝未声明的 launcher 和嵌套压缩包，保留仓库相对路径与 Exodus 符号链接，并在清单中记录每个 launcher 来自哪个配置对象，同时写入 checksum、许可证和源码版本。输出路径以 `.zip` 结尾时生成独立 ZIP；否则生成内容相同的目录。

Python 包版本由 [setuptools-scm](https://setuptools-scm.readthedocs.io/) 根据仓库 tag 自动生成，tag 是版本信息的唯一来源。构建标签版本前，应先规范化并比较 tag 与已经安装的 `bsworld` 包版本。在 GitHub Actions 中，使用 `GITHUB_REF_NAME` 获取 tag，并检出完整 Git 历史与标签，确保版本信息能够正确生成；缺少 tag 或版本不一致时，应停止发布构建。

发布到 GitHub 时，通过相同参数传入已经准备好的源码工作区路径。测试通过后，使用 `create_binary_release.py` 的 `--output dist/bsworld-prebuilt-<tag>.zip` 参数生成单个 ZIP，再将它附加到对应的 GitHub Release。用户使用 `scripts/install_binary_release.py` 安装该产物，pytest 不参与安装。GitHub Actions 工作流可以通过环境变量提供 `NUTTX_DIR`、`NUTTX_APPS_DIR`、`ZEPHYR_WORKSPACE` 和 `BSIM_OUT_DIR`，并将这些路径明确传给构建和打包脚本。

## 测试覆盖率

分支覆盖率由 [coverage.py](https://coverage.readthedocs.io/) 统计，并在 `pyproject.toml` 的 `[tool.coverage.run]` 中启用。

```sh
# 只统计单元测试覆盖率，速度快，不需要固件或 BabbleSim
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
python -m coverage run -m pytest \
  -p pytest_asyncio.plugin -p bsworld.plugin tests/unit
python -m coverage report

# 手动准备运行依赖；仿真测试不插入覆盖率探针
export BSIM_OUT_PATH=/tmp/bsworld/build/babblesim/bsim
export BSIM_COMPONENTS_PATH=$PWD/components/babblesim/components
export BSIM_BASE_PATH=$BSIM_COMPONENTS_PATH
export BSIM_BUILD_FAIL_ASAP=1
make -C components/babblesim everything
pytest tests/integration/ -n auto
```

这组命令会先启动覆盖率记录，再由 pytest 导入项目代码；同时关闭无关的第三方插件自动加载，只显式启用测试所需的 asyncio 和 BSWorld 插件。最终报告会统计整个 `bsworld` 包，包括 runtime 调度器。
