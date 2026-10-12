# BSWorld NuttX BTSak Tests

[English](README.md) | [中文](README.zh-CN.md)


This directory contains end-to-end tests for the stock NuttX `btsak` Application. BSWorld does not keep custom Bluetooth LE Application source here. The tests build and run one NuttX image that includes `btsak`, then use process shell commands to choose the role for each process.

Application build instructions and prebuilt artifact locations are documented in [source/README.md](source/README.md). For first-time NuttX environment setup, start with [../README.md](../README.md).

## Files

- `devices.py`: reusable `NuttXProcessProfile` definitions for scanner and advertiser roles. Both roles use the same NuttX image.
- `test_btsak_scan_advertise.py`: end-to-end scenarios covering one scanner discovering one or more advertisers.
- `build.sh`: independently builds and packages the test image.
- `source/`: build inputs and details for the stock NuttX image.
- `prebuilt/`: generated, expanded Exodus runtimes consumed by this test suite.

`NuttXProcessProfile` entries set `controller_address`. BSWorld passes that address to the Virtual Controller before the Host connects.

## Shell Commands

NuttX profiles enable the process shell by default. After `await topo.start()` establishes the initial PHY synchronization boundary, the test issues role commands through the process shell. Advertiser processes run:

```sh
ifup bnep0
bt bnep0 advertise start
```

Scanner processes run:

```sh
ifup bnep0
bt bnep0 scan start
sleep 1
bt bnep0 scan get
...
```

The scanner test waits for non-zero addresses printed by `bt bnep0 scan get`. The stock `btsak` advertiser currently uses a fixed scan-response name, so the test validates discovery through scan table entries instead of custom names. Role commands are defined in the test and can be issued together with `shell.run_many(...)` or individually with `shell.run(...)`.

## Test Cases

- `test_nuttx_btsak_scanner_finds_advertiser`: one scanner discovers one advertiser.
- `test_nuttx_btsak_shell_commands_can_stage_scan`: the test starts both process shells, then issues role commands in explicit stages.
- `test_nuttx_btsak_scanner_finds_multiple_advertisers`: one scanner discovers two advertisers.
- `test_nuttx_btsak_targeted_interference_isolates_and_recovers`: three timed CW sources cover advertising channels 37, 38, and 39. Per-path attenuation places them next to one scanner while isolating a second scanner; the protected scanner keeps receiving during the interference window, and the jammed scanner recovers after the window closes.

The interference case uses the same unmodified NuttX image as the other cases. Only the BSWorld RF topology changes.

## Run

```sh
tests/integration/nuttx/btsak/build.sh \
  --nuttx-dir /path/to/nuttx \
  --nuttx-apps-dir /path/to/nuttx-apps \
  --bsim-out-dir /tmp/bsworld/build/babblesim/bsim
pytest tests/integration/nuttx/btsak -q --no-ellisys
```

The tests require the generated `prebuilt/nuttx/exodus/bin/nuttx` launcher.
