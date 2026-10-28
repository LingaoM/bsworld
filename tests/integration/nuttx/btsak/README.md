# BSWorld NuttX BTSak Tests

[English](README.md) | [简体中文](README.zh-CN.md)

Runs the stock NuttX `btsak` and uses shell commands to make each process an advertiser or a scanner. See [source/README.md](source/README.md) for the build.

## Shell Commands

Advertiser processes:

```sh
ifup bnep0
bt bnep0 advertise start
```

Scanner processes:

```sh
ifup bnep0
bt bnep0 scan start
sleep 1
bt bnep0 scan get
...
```

## Test Cases

- `test_nuttx_btsak_scanner_finds_advertiser`: one scanner discovers one advertiser.
- `test_nuttx_btsak_shell_commands_can_stage_scan`: both shells start first, then role commands are issued in stages.
- `test_nuttx_btsak_scanner_finds_multiple_advertisers`: one scanner discovers two advertisers.
- `test_nuttx_btsak_targeted_interference_isolates_and_recovers`: CW interference on the advertising channels blocks only one scanner, which recovers afterwards.

## Run

In the [Docker test image](../../../../docker/README.md#select-a-suite), use `tests/integration/nuttx/btsak`. Natively:

```sh
source "$BSWORLD_ROOT/.venv/bin/activate"
export BSWORLD_NUTTX_BTSAK_BIN="$NUTTX_DIR/nuttx"
cd "$BSWORLD_ROOT"
pytest tests/integration/nuttx/btsak -q
```
