# NuttX NimBLE 测试

[English](README.md) | [中文](README.zh-CN.md)


这个目录保存 BSWorld 对 [Apache NimBLE](https://github.com/apache/mynewt-nimble) Host 的 NuttX 集成测试。这里不维护自定义 NimBLE 业务程序，而是直接运行 nuttx-apps 中已有的示例。

当前测试会启动：

- `examples/nimble_bleprph`：作为 Peripheral。
- `examples/nimble_blecent`：作为 Central。

Peripheral 会广播原生示例默认的 `NuttX NimBLE PRPH` 名称和 Alert Notification Service UUID。Central 负责扫描、发现广播、建立连接、执行服务发现并订阅通知。测试只检查这些 NuttX 示例自身输出的日志，不依赖 BSWorld 添加的特殊标记。

两个角色使用同一份 NuttX 镜像，进程配置默认启用 Shell。`await topo.start()` 建立初始 PHY 同步边界后，测试通过 `process.shell.run_many(...)` 发送 `ifup bnep0` 和对应的 `bleprph` 或 `blecent` 命令。角色命令由测试用例指定，不放在进程配置中。

固件产物的构建方式见 [`source/README.zh-CN.md`](source/README.zh-CN.md)。首次准备 NuttX 环境时，先看 [../README.zh-CN.md](../README.zh-CN.md)。

## 文件职责

- `devices.py`：定义 Central 和 Peripheral 使用的 `NuttXProcessProfile`。两个角色使用同一份 NuttX 镜像。
- `test_central_peripheral.py`：端到端测试，验证 Central 能发现 Peripheral、建立连接并完成 NimBLE 示例默认的服务发现流程。
- `build.sh`：独立构建并打包测试镜像。
- `source/`：NuttX 上游 NimBLE 镜像的构建配置和说明。
- `prebuilt/`：测试直接使用的、已经展开的 Exodus 运行目录。

## Shell 命令

Peripheral 进程启动后执行：

```sh
ifup bnep0
bleprph
```

Central 进程启动后执行：

```sh
ifup bnep0
blecent
```

测试会等待 NuttX 示例自身输出的连接、服务发现和订阅日志。

## 运行

```sh
tests/integration/nuttx/nimble/build.sh \
  --nuttx-dir /path/to/nuttx \
  --nuttx-apps-dir /path/to/nuttx-apps \
  --bsim-out-dir /tmp/bsworld/build/babblesim/bsim
pytest tests/integration/nuttx/nimble -q --no-ellisys
```

测试需要已经生成的 `prebuilt/nuttx/exodus/bin/nuttx` launcher。
