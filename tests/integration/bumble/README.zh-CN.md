# Bumble 集成测试

[English](README.md) | [简体中文](README.zh-CN.md)

在 pytest 的 asyncio event loop 中运行 [Bumble](https://github.com/google/bumble) Host，与测试共用仿真时钟。每个设备连接一个独立的虚拟 Controller。场景：

- 传统广播和被动扫描；
- 广播信道上的定向 CW 干扰与恢复；
- Bumble Central 与 Peripheral 建立连接；
- 周期广播与同步。

[已发布的 Docker 镜像](../../../docker/README.zh-CN.md#运行测试)中使用 `pytest tests/integration/bumble`。Bumble 随 BSWorld 安装；本机按[本地 Linux 环境搭建](../../../docs/zh-CH/README.md#本地-linux)准备后运行：

```sh
cd "$BSWORLD_ROOT"
source .venv/bin/activate
pytest tests/integration/bumble -n auto
```

## 添加场景

在对应场景目录添加异步 pytest 测试。`topo.start()` 前调用 [common/](common/) 中的 `add_bumble_controller()`，启动后调用 `open_bumble_device()`；两个设备可直接用 `open_bumble_pair()`。
