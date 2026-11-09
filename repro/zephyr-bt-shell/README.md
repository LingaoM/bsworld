# Zephyr Bluetooth Shell Reproductions

These tests reproduce bugs in the Zephyr Bluetooth Host shell
(`subsys/bluetooth/host/shell`) and mismatches with its documentation
(`doc/services/connectivity/bluetooth/shell/host`). Each test checks the
correct behavior, so it fails before the fix and passes after it. The tests
run the `tests/bluetooth/shell` application on `nrf52_bsim/native` in
BabbleSim through BSWorld.

| Test | Problem | Issue | Fix |
|---|---|---|---|
| [test_iso_big.py](test_iso_big.py) | `iso create-big`, `sync-big` and `term-big` are unknown commands; `create-big enc` without a code crashes; `sync-big` rejects all three options together | A | A |
| [test_l2cap_ecred.py](test_l2cap_ecred.py) | `l2cap ecred-reconfigure` without an MTU crashes | B | B |
| [test_iso_cig_create.py](test_iso_cig_create.py) | `iso cig_create` reads the SDU, PHY and RTN from the wrong arguments | C | C |
| [test_scan_and_per_adv.py](test_scan_and_per_adv.py) | `bt scan --window` checks the interval; `bt per-adv-param tx-power` sets an advertising option; unbalanced brackets in help text | - | D |
| [test_doc_examples.py](test_doc_examples.py) | Documented commands that the shell rejects or treats differently | - | E |

`test_doc_examples.py` passes before and after the documentation fix. Each of
its tests runs the documented form next to the form the shell accepts.

## Prepare

Set up BSWorld and build BabbleSim as in the [BSWorld README](../../README.md#local-linux),
and prepare a Zephyr workspace with the BabbleSim variables exported.

## Build

The complete image contains the Host, the Zephyr Controller and the radio. It
uses the `bluetooth.native_shell` configuration and [iso-data.conf](iso-data.conf):

```sh
REPRO="$BSWORLD_ROOT/repro/zephyr-bt-shell"
cd "$ZEPHYR_BASE"
west build -p always -b nrf52_bsim/native -d build/bt_shell tests/bluetooth/shell -- \
  -DEXTRA_CONF_FILE="xterm-native-shell.conf;$REPRO/iso-data.conf" \
  -DEXTRA_DTC_OVERLAY_FILE=xterm-native-shell.overlay
export ZEPHYR_BT_SHELL_EXE="$ZEPHYR_BASE/build/bt_shell/zephyr/zephyr.exe"
```

With the default 9-byte Controller ISO TX buffer, the largest BIS PDU is
1 byte. LE Create BIG then fails with status 0x12 and CIS data does not fit.
`iso-data.conf` sizes the buffers for the 247-byte SDUs of the ISO shell. Only
`test_big_broadcast_and_sync` and `test_cig_create_reads_sdu_phy_and_rtn`
send ISO data.

The Host-only image connects to a BSWorld Controller over an HCI socket, and
BSWorld writes the HCI traffic to `hciN.snoop`. `test_per_adv_tx_power` needs
it: the Zephyr Controller does not add the TX power to periodic advertising
yet (see the FIXME in `ll_adv_sync_param_set()`), so the test checks the HCI
command that the Host sends.

```sh
west build -p always -b nrf52_bsim/native -d build/bt_shell_host tests/bluetooth/shell -- \
  -DEXTRA_CONF_FILE="xterm-native-shell.conf;$REPRO/host-only.conf" \
  -DEXTRA_DTC_OVERLAY_FILE="xterm-native-shell.overlay;$REPRO/host-only.overlay"
export ZEPHYR_BT_SHELL_HOST_EXE="$ZEPHYR_BASE/build/bt_shell_host/zephyr/zephyr.exe"
```

Without `ZEPHYR_BT_SHELL_HOST_EXE`, `test_per_adv_tx_power` is skipped.

## Run

```sh
cd "$BSWORLD_ROOT"
source .venv/bin/activate
pytest repro/zephyr-bt-shell
```

Each test writes the console of every shell to
`/tmp/run-<timestamp>/<uid>/log/<test file>/<test>/<label>/<label>.log`.
When a shell crashes, `bsworld.log` in the same test directory reports
`exited unexpectedly (rc=-11)`.

## Results

Zephyr 0534e997eac, with each fix applied on its own. The host shell files
are the same as on main 5b375948321.

| Test | Before | A | B | C | D | All |
|---|---|---|---|---|---|---|
| test_iso_big.py (5 tests) | fail | pass | fail | fail | fail | pass |
| test_l2cap_ecred.py | fail | fail | pass | fail | fail | pass |
| test_iso_cig_create.py | fail | fail | fail | pass | fail | pass |
| test_scan_and_per_adv.py (3 tests) | fail | fail | fail | fail | pass | pass |
| test_doc_examples.py (4 tests) | pass | pass | pass | pass | pass | pass |
