# Native TrouBLE Test

[English](README.md) | [简体中文](README.zh-CN.md)

This test runs two [TrouBLE](https://github.com/embassy-rs/trouble) Rust Hosts as native Linux processes. Each Host joins BabbleSim directly and reaches its Virtual Controller over an H:4 Unix socket, with its timers running on simulation time. The Host stack and the Battery Service applications come from a pinned upstream commit; [`source/src/bsim/`](source/src/bsim) supplies the Unix transport, executor, and BabbleSim clock.

## Validated Scenario

`test_trouble_native_hosts_connect_discover_read_and_notify` runs against both Virtual Controller implementations (`[zephyr]` and `[bscontroller]`) and validates:

1. The peripheral advertises and accepts a connection from the central.
2. The central discovers the Battery Service and reads the Battery Level characteristic.
3. The central subscribes and receives notifications well past connection setup.

## Build and Run

We recommend the [Docker test image](../../../docker/README.md#select-a-suite), using `tests/integration/trouble` as the pytest target.

For native Linux, install a Rust toolchain with [rustup](https://rustup.rs/), retain the BabbleSim and Controller exports from the repository [README](../../../README.md), then run from the repository root:

```sh
cargo build --locked --manifest-path tests/integration/trouble/source/Cargo.toml

cd "$BSWORLD_ROOT"
source .venv/bin/activate
pytest tests/integration/trouble -q
```

Set `BSWORLD_TROUBLE_NATIVE_BIN` to the `ble_bas` binary when using `CARGO_TARGET_DIR` or a release build; otherwise the test uses `source/target/debug/ble_bas`.

The transport, executor, and clock have unit tests that need no simulator:

```sh
cargo test --locked --manifest-path tests/integration/trouble/source/Cargo.toml
```

Application logs are stored as `trouble/central/central.log` and `trouble/peripheral/peripheral.log`. HCI BTSnoop captures and BabbleSim RF traces are archived with the other per-test files described in [Logs, Traces, and Packet Captures](../../../docs/artifacts.md).

## Adding Scenarios

Use [test_trouble_native.py](test_trouble_native.py) as the starting point: register each native Host role before `topo.start()`, then verify connection and application events with `wait_log()`. Roles and application behavior are implemented by the Rust executable; rebuild it when those behaviors change.

## License

The tests and the adapter in this directory are licensed under Apache License 2.0. TrouBLE is available under MIT or Apache License 2.0, and `source/src/bsim/` retains the MIT OR Apache-2.0 license of its original form. Review [Third-Party Notices](../../../THIRD_PARTY_NOTICES.md) before distributing binaries.
