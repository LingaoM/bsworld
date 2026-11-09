# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Shell documentation examples that do not match the shell (PR E).

These tests pass before and after the documentation fix. Each one runs the
command form from the documentation next to the form the shell accepts.
"""

import re

from conftest import ADDRESS


async def test_scan_filter_command_name(single):
    # gap.rst names the command "bt scan-set-filter".
    await single.run("bt scan-set-filter rssi -40", until="unknown parameter")
    await single.run("bt scan-filter-set rssi -40", until="RSSI cutoff set at -40 dB")


async def test_iso_help(single):
    # iso.rst lists the commands with "iso --help". With CONFIG_SHELL_GETOPT,
    # the shell passes --help to the iso handler.
    await single.run("iso --help", until="iso unknown parameter: --help")
    await single.run("iso", until="Subcommands:")


async def test_iso_listen_security_level(single):
    # iso.rst shows listen with a [security level] argument.
    await single.run("iso listen txrx 2", until="wrong parameter count")
    await single.run("iso listen txrx")


async def test_scan_with_filter_accept_list(trio):
    listed, other, central = trio
    listed_address = await listed.identity()
    other_address = await other.identity()
    for shell in (listed, other):
        await shell.run("bt advertise on identity", until="Advertising started")
    await central.run(f"bt fal-add {listed_address}")

    def reported(out):
        return set(re.findall(rf"\[DEVICE\]: ({ADDRESS})", out))

    # gap.rst: "bt scan on fal". bt scan takes options before on, so fal is
    # ignored and the scanner reports every device.
    out = await central.run("bt scan on fal", settle=2.0)
    await central.run("bt scan off", until="Scan successfully stopped")
    assert {listed_address, other_address} <= reported(out), out

    out = await central.run("bt scan --fal on", settle=2.0)
    await central.run("bt scan off", until="Scan successfully stopped")
    assert reported(out) == {listed_address}, out
