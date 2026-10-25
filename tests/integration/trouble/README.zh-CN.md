# 原生 TrouBLE 测试

[English](README.md) | [简体中文](README.zh-CN.md)

本测试将两个 [TrouBLE](https://github.com/embassy-rs/trouble) Rust Host 作为原生 Linux 进程运行。每个 Host 直接加入 BabbleSim，通过 H:4 Unix socket 连接到各自的 Virtual Controller，定时器运行在仿真时间上。Host 协议栈与 Battery Service 应用来自固定的上游提交；[`source/src/bsim/`](source/src/bsim) 提供 Unix 传输、执行器与 BabbleSim 时钟。

## 已验证场景

`test_trouble_native_hosts_connect_discover_read_and_notify` 针对两种 Virtual Controller 实现（`[zephyr]` 与 `[bscontroller]`）运行，验证：

1. peripheral 发起广播并接受 central 的连接。
2. central 发现 Battery Service 并读取 Battery Level 特征。
3. central 订阅后持续接收通知，覆盖连接建立之后的行为。

## 构建与运行

推荐使用 [Docker 测试镜像](../../../docker/README.zh-CN.md#选择测试套件)，pytest 目标为 `tests/integration/trouble`。

在本地 Linux 上，用 [rustup](https://rustup.rs/) 安装 Rust 工具链，保留仓库 [README](../../../docs/zh-CH/README.md) 中的 BabbleSim 与 Controller 环境变量，然后在仓库根目录执行：

```sh
cargo build --locked --manifest-path tests/integration/trouble/source/Cargo.toml

cd "$BSWORLD_ROOT"
source .venv/bin/activate
pytest tests/integration/trouble -q
```

使用 `CARGO_TARGET_DIR` 或 release 构建时，将 `BSWORLD_TROUBLE_NATIVE_BIN` 设为 `ble_bas` 二进制路径；否则测试使用 `source/target/debug/ble_bas`。

传输、执行器与时钟带有单元测试，无需仿真器：

```sh
cargo test --locked --manifest-path tests/integration/trouble/source/Cargo.toml
```

应用日志保存为 `trouble/central/central.log` 和 `trouble/peripheral/peripheral.log`。HCI BTSnoop 抓包与 BabbleSim 射频 trace 与其他按用例归档的文件一起保存，详见[日志、Trace 与抓包](../../../docs/zh-CH/artifacts.md)。

## 许可

本目录下的测试与适配层以 Apache License 2.0 授权。TrouBLE 以 MIT 或 Apache License 2.0 提供，`source/src/bsim/` 保留其原始形态的 MIT OR Apache-2.0 许可。分发二进制前请查阅[第三方声明](../../../THIRD_PARTY_NOTICES.md)。
