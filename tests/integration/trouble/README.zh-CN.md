# 原生 TrouBLE 测试

[English](README.md) | [简体中文](README.zh-CN.md)

将两个 [TrouBLE](https://github.com/embassy-rs/trouble) Rust Host 作为原生 Linux 进程运行，各自连接一个虚拟 Controller。[`source/src/bsim/`](source/src/bsim) 提供 Unix 传输、执行器和 BabbleSim 时钟。

## 已验证场景

`test_trouble_native_hosts_connect_discover_read_and_notify`，每种 Controller 各跑一次：

1. peripheral 发起广播并接受 central 的连接。
2. central 发现 Battery Service 并读取 Battery Level 特征。
3. central 订阅并接收通知。

## 构建与运行

[Docker 测试镜像](../../../docker/README.zh-CN.md#选择测试套件)中使用 `tests/integration/trouble`。本机先用 [rustup](https://rustup.rs/) 安装 Rust，再在仓库根目录执行：

```sh
cargo build --locked --manifest-path tests/integration/trouble/source/Cargo.toml

cd "$BSWORLD_ROOT"
source .venv/bin/activate
pytest tests/integration/trouble -q
```

测试默认使用 `source/target/debug/ble_bas`，其他构建产物通过 `BSWORLD_TROUBLE_NATIVE_BIN` 指定。

适配层单元测试：

```sh
cargo test --locked --manifest-path tests/integration/trouble/source/Cargo.toml
```

日志位于 `trouble/<角色>/`，其余见[产物目录结构](../../../docs/zh-CH/artifacts.md)。

## 添加场景

以 [test_trouble_native.py](test_trouble_native.py) 为起点，在 `topo.start()` 前登记各 Host 角色，启动后用 `wait_log()` 验证事件。角色行为在 Rust 可执行文件中实现。

## 许可

本目录下的测试与适配层以 Apache License 2.0 授权。TrouBLE 以 MIT 或 Apache License 2.0 提供，`source/src/bsim/` 保留其原始形态的 MIT OR Apache-2.0 许可。分发二进制前请查阅[第三方声明](../../../THIRD_PARTY_NOTICES.md)。
