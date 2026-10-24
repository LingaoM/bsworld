# NuttX NimBLE Tests

[English](README.md) | [简体中文](README.zh-CN.md)

This directory contains BSWorld tests for the [Apache NimBLE](https://github.com/apache/mynewt-nimble) Host running as stock NuttX apps examples.

The current test starts:

- `examples/nimble_bleprph` as the peripheral.
- `examples/nimble_blecent` as the central.

The peripheral advertises the stock `NuttX NimBLE PRPH` name and Alert Notification Service UUID. The central scans, finds that advertisement, connects, performs service discovery, and subscribes to notifications. The test waits for the connection, service discovery, and subscription logs printed by these NuttX examples.

Firmware build instructions live in [`source/README.md`](source/README.md). For first-time NuttX environment setup, start with [../README.md](../README.md).

## Shell Commands

NuttX profiles enable the process shell by default. After `await topo.start()` establishes the initial PHY synchronization boundary, the test issues role commands through the process shell. Peripheral processes run:

```sh
ifup bnep0
bleprph
```

Central processes run:

```sh
ifup bnep0
blecent
```

## Run

We recommend the [Docker test image](../../../../docker/README.md#select-a-suite), using `tests/integration/nuttx/nimble` as the pytest target.

For native Linux, compile with [source/README.md](source/README.md), retain the BabbleSim and Controller variables, then switch back to the BSWorld Python environment and run:

```sh
source "$BSWORLD_ROOT/.venv/bin/activate"
export BSWORLD_NUTTX_NIMBLE_BIN="$NUTTX_NIMBLE_DIR/nuttx"
cd "$BSWORLD_ROOT"
pytest tests/integration/nuttx/nimble -q
```
