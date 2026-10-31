# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

import re

import pytest
from tests.integration.zephyr.shell_common import shell_identity


@pytest.mark.parametrize("active", [False, True], ids=["passive", "active"])
async def test_scan(shell_pair, active):
    """Passive scanning reports non-connectable advertising; active scanning
    obtains the SCAN_RSP that carries the device name."""
    peripheral, central = shell_pair
    address = re.escape(await shell_identity(peripheral))
    if active:
        # Legacy connectable advertising carries the device name in SCAN_RSP,
        # reported as event type 4 with the SR flag set.
        await peripheral.shell.run("bt advertise on identity")
        pattern = (
            rf"\[DEVICE\]: {address}, AD evt type 4, "
            r".*BSWorld shell C:1 S:1 D:0 SR:1"
        )
    else:
        # The shell keeps its name in SCAN_RSP, so "nconn" sends ADV_SCAN_IND:
        # scannable, but reported as not connectable.
        await peripheral.shell.run("bt advertise nconn identity")
        pattern = rf"\[DEVICE\]: {address}, AD evt type 2, .*C:0 S:1 D:0 SR:0"
    await peripheral.wait_log("Advertising started")
    await central.shell.run("bt scan on" if active else "bt scan passive")
    await central.wait_log(pattern)
    await central.shell.run("bt scan off")
    await central.wait_log("Scan successfully stopped")
