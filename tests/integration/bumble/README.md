# Bumble Integration Tests

[English](README.md) | [简体中文](README.zh-CN.md)

Runs the [Bumble](https://github.com/google/bumble) Host inside the pytest asyncio event loop, sharing the simulation clock with the test. Each device has its own Virtual Controller. Scenarios:

- legacy advertising and passive scanning;
- targeted CW interference on the advertising channels and recovery;
- connection between a Bumble central and peripheral;
- periodic advertising and synchronization.

In the [published Docker image](../../../docker/README.md#run-tests), use `pytest tests/integration/bumble`. Bumble is installed with BSWorld; natively, after the [local Linux setup](../../../README.md#local-linux), run:

```sh
cd "$BSWORLD_ROOT"
source .venv/bin/activate
pytest tests/integration/bumble -n auto
```

## Adding Scenarios

Add an async pytest test in the relevant scenario directory. Call `add_bumble_controller()` from [common/](common/) before `topo.start()` and `open_bumble_device()` after it; `open_bumble_pair()` does both for two devices.
