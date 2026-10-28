# NuttX NimBLE Tests

[English](README.md) | [简体中文](README.zh-CN.md)

Runs the [Apache NimBLE](https://github.com/apache/mynewt-nimble) examples from nuttx-apps: `nimble_bleprph` as the Peripheral and `nimble_blecent` as the Central. The Central scans, connects, discovers services and subscribes to notifications. See [source/README.md](source/README.md) for the build.

## Shell Commands

Peripheral processes:

```sh
ifup bnep0
bleprph
```

Central processes:

```sh
ifup bnep0
blecent
```

## Run

In the [Docker test image](../../../../docker/README.md#select-a-suite), use `tests/integration/nuttx/nimble`. Natively:

```sh
source "$BSWORLD_ROOT/.venv/bin/activate"
export BSWORLD_NUTTX_NIMBLE_BIN="$NUTTX_NIMBLE_DIR/nuttx"
cd "$BSWORLD_ROOT"
pytest tests/integration/nuttx/nimble -q
```
