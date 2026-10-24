# 开发检查

[English](../development.md) | [简体中文](development.md)

在仓库根目录运行 BSWorld 的单元测试、静态检查和覆盖率统计。使用[已发布的 Docker 镜像](../../docker/README.zh-CN.md#运行测试)可以减少环境准备；需要本机 Python 环境时，按照 README 的[本地 Linux 环境搭建](README.md#本地-linux)操作。

## 单元测试

使用 Docker：

```sh
sudo docker run --rm \
  --mount "type=bind,src=$PWD,dst=/workspace,readonly" \
  --env PYTHONDONTWRITEBYTECODE=1 \
  -e PYTHONPATH=/workspace \
  ghcr.io/xiaomi/bsworld:latest pytest tests/unit -q -p no:cacheprovider
```

使用本地虚拟环境：

```sh
cd "$BSWORLD_ROOT"
source .venv/bin/activate
pytest tests/unit -q
```

单元测试覆盖环境与产物解析、拓扑和 Controller 生命周期、BabbleSim 命令生成、RF 配置、仿真时间调度、FIFO 时钟通信和日志采集。端到端 Bluetooth 行为由 `tests/integration/` 覆盖。

## 静态检查

使用 Docker：

```sh
sudo docker run --rm \
  --mount "type=bind,src=$PWD,dst=/workspace,readonly" \
  -e PYTHONPATH=/workspace \
  ghcr.io/xiaomi/bsworld:latest ruff check --no-cache src tests
```

使用本地虚拟环境：

```sh
ruff check src tests
```

在本地应用安全的自动修复：

```sh
ruff check --fix src tests
```

## 测试覆盖率

分支覆盖率已在 `pyproject.toml` 中启用。在本地环境中统计单元测试覆盖率：

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
python -m coverage run -m pytest \
  -p pytest_asyncio.plugin -p bsworld.plugin tests/unit
python -m coverage report
```

构建所需固件后，单独运行集成测试：

```sh
pytest tests/integration/ -n auto
```

覆盖率报告包含完整的 `bsworld` Python 包，包括 runtime 调度器。
