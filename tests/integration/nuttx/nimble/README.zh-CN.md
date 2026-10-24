# NuttX NimBLE 测试

[English](README.md) | [简体中文](README.zh-CN.md)

这个目录保存 BSWorld 对 [Apache NimBLE](https://github.com/apache/mynewt-nimble) Host 的 NuttX 集成测试。测试运行 nuttx-apps 中的 NimBLE 示例。

当前测试会启动：

- `examples/nimble_bleprph`：作为 Peripheral。
- `examples/nimble_blecent`：作为 Central。

Peripheral 会广播原生示例默认的 `NuttX NimBLE PRPH` 名称和 Alert Notification Service UUID。Central 负责扫描、发现广播、建立连接、执行服务发现并订阅通知。测试会等待这些 NuttX 示例输出的连接、服务发现和订阅日志。

固件产物的构建方式见 [`source/README.zh-CN.md`](source/README.zh-CN.md)。首次准备 NuttX 环境时，先看 [../README.zh-CN.md](../README.zh-CN.md)。

## Shell 命令

NuttX 进程配置默认启用 Shell。`await topo.start()` 建立初始 PHY 同步边界后，测试通过进程 Shell 下发角色命令。Peripheral 进程执行：

```sh
ifup bnep0
bleprph
```

Central 进程执行：

```sh
ifup bnep0
blecent
```

## 运行

推荐使用 [Docker 测试镜像](../../../../docker/README.zh-CN.md#选择测试套件)，将 pytest 测试路径设为 `tests/integration/nuttx/nimble`。

本机 Linux 按 [source/README.zh-CN.md](source/README.zh-CN.md) 构建，保留 BabbleSim 和 Controller 变量，再切回 BSWorld Python 环境并运行：

```sh
source "$BSWORLD_ROOT/.venv/bin/activate"
export BSWORLD_NUTTX_NIMBLE_BIN="$NUTTX_NIMBLE_DIR/nuttx"
cd "$BSWORLD_ROOT"
pytest tests/integration/nuttx/nimble -q
```
