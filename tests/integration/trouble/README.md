# Native TrouBLE Test

[English](README.md) | [简体中文](README.zh-CN.md)

Runs two [TrouBLE](https://github.com/embassy-rs/trouble) Rust Hosts as native Linux processes, each with its own Virtual Controller. [`source/src/bsim/`](source/src/bsim) provides the Unix transport, executor and BabbleSim clock.

## Validated Scenario

`test_trouble_native_hosts_connect_discover_read_and_notify`, once per Controller:

1. The peripheral advertises and accepts a connection from the central.
2. The central discovers the Battery Service and reads the Battery Level characteristic.
3. The central subscribes and receives notifications.

## Build and Run

In the [Docker test image](../../../docker/README.md#select-a-suite), use `tests/integration/trouble`. Natively, install Rust with [rustup](https://rustup.rs/), then run from the repository root:

```sh
cargo build --locked --manifest-path tests/integration/trouble/source/Cargo.toml

cd "$BSWORLD_ROOT"
source .venv/bin/activate
pytest tests/integration/trouble -q
```

The test uses `source/target/debug/ble_bas` by default; set `BSWORLD_TROUBLE_NATIVE_BIN` for other build outputs.

Unit tests for the adapter:

```sh
cargo test --locked --manifest-path tests/integration/trouble/source/Cargo.toml
```

Logs are under `trouble/<role>/`; see [artifacts](../../../docs/artifacts.md) for the rest.

## Adding Scenarios

Start from [test_trouble_native.py](test_trouble_native.py): register each Host role before `topo.start()`, then verify events with `wait_log()`. Role behavior lives in the Rust executable.

## License

The tests and the adapter in this directory are licensed under Apache License 2.0. TrouBLE is available under MIT or Apache License 2.0, and `source/src/bsim/` retains the MIT OR Apache-2.0 license of its original form. Review [Third-Party Notices](../../../THIRD_PARTY_NOTICES.md) before distributing binaries.
