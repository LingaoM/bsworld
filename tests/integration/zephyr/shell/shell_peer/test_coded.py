# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

from tests.integration.zephyr.shell.shell_peer.common import (
    connect,
    disconnect,
    wait_both,
)
from tests.integration.zephyr.shell_common import shell_identity


async def test_coded_phy_extended_connection(shell_pair):
    """Connect from LE Coded extended advertising without any 1M scanning."""
    peripheral, central = shell_pair
    address = await shell_identity(peripheral)
    await peripheral.shell.run("bt adv-create conn-nscan ext-adv coded identity")
    await peripheral.wait_log("Created adv id: 0")
    await peripheral.shell.run("bt adv-start")
    await peripheral.wait_log(r"Advertiser\[0\].* set started")
    await connect(
        peripheral, central, address=address, options="coded no-1m", advertise=False
    )
    for device in (central, peripheral):
        await device.shell.run("bt info")
        await device.wait_log("LE PHY: TX PHY LE Coded, RX PHY LE Coded")
    # Peripheral-initiated PHY Update; the Central has not set a preference.
    await peripheral.shell.run("bt phy-update 2")
    await wait_both((central, peripheral), "LE PHY updated: TX PHY LE 2M, RX PHY LE 2M")
    await disconnect(peripheral, central)
