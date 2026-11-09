# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""bt scan --window, bt per-adv-param tx-power and help text (PR D).

bt scan checks the interval instead of the window against UINT16_MAX, and
bt per-adv-param tx-power sets an advertising option that periodic
advertising ignores. The help of bt scan --interval and l2cap recv lacks a
closing bracket.
"""


async def test_scan_window_too_large(single):
    # 70000 does not fit in 16 bits. Before the fix it is truncated to 4464,
    # which is larger than the default interval, and scanning fails with
    # err -22.
    await single.run("bt scan --window 70000 on", until="Window value too large|scan")
    await single.wait("Window value too large")


async def test_per_adv_tx_power(host_only):
    # The Zephyr Controller does not add the TX power to periodic advertising
    # yet (see the FIXME in ll_adv_sync_param_set()), so a synchronized device
    # reports tx_power 127 either way. Check the HCI command instead: the
    # Include TxPower bit (bit 6) of Periodic_Advertising_Properties.
    await host_only.run("bt adv-create nconn-nscan ext-adv", until="Created adv id")
    await host_only.run("bt per-adv-param 640 780 tx-power")
    commands = host_only.hci_commands(0x203E) + host_only.hci_commands(0x2086)
    assert commands, "no LE Set Periodic Advertising Parameters command captured"
    properties = int.from_bytes(commands[-1][5:7], "little")
    assert properties & 0x0040, f"Periodic_Advertising_Properties 0x{properties:04x}"


async def test_help_brackets(single):
    out = " ".join(
        (await single.run("bt scan -h", until="<value: on, passive, off>")).split()
    )
    assert "[--interval <n * 0.625 ms>]" in out, out
    # Too many arguments make the shell print the help of the command.
    out = " ".join((await single.run("l2cap recv 1 2", until="recv - ")).split())
    assert "[delay (in milliseconds)]" in out, out
