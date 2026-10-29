# QEMU NimBLE Linux 测试

[English](README.md) | [简体中文](README.zh-CN.md)

在 [QEMU Linux Guest](../README.zh-CN.md) 中运行 Apache NimBLE 上游的 Linux Host 示例，Bumble 作为对端。

## 测试场景

`test_qemu_nimble_linux_advertises_and_accepts_connection`：NimBLE 以 `AA:BB:CC:DD:EE:FE` 和设备名 `nimble` 广播，Bumble Central 连接后断开。

## 运行

```sh
cd "$BSWORLD_ROOT"
source .venv/bin/activate
pytest tests/integration/qemu/nimble -q
```

QEMU console 位于 `qemu/nimble/qemu_nimble.log`，其余见[产物目录结构](../../../../docs/zh-CH/artifacts.md)。

## 许可证

本目录的测试使用 Apache License 2.0，其余见[上级许可证说明](../README.zh-CN.md#许可证)。
