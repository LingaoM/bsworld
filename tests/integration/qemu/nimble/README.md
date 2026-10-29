# QEMU NimBLE Linux Test

[English](README.md) | [简体中文](README.zh-CN.md)

Runs the upstream Apache NimBLE Linux Host example in the [QEMU Linux guest](../README.md). Bumble is the peer.

## Validated Scenario

`test_qemu_nimble_linux_advertises_and_accepts_connection`: NimBLE advertises as `nimble` from `AA:BB:CC:DD:EE:FE`, and a Bumble Central connects and disconnects.

## Run

```sh
cd "$BSWORLD_ROOT"
source .venv/bin/activate
pytest tests/integration/qemu/nimble -q
```

The QEMU console is under `qemu/nimble/qemu_nimble.log`; see [artifacts](../../../../docs/artifacts.md) for the rest.

## License

The tests in this directory use Apache License 2.0. See the [parent license notes](../README.md#license).
