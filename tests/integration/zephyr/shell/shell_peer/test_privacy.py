# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Bonding, then reconnection through Controller-based address resolution."""

from tests.integration.zephyr.shell.shell_peer.common import (
    connect,
    disconnect,
    wait_both,
)
from tests.integration.zephyr.shell_common import shell_identity


async def _encrypt_with_stored_key(peripheral, central) -> None:
    # Encryption restarts from the stored LTK without pairing again.
    await central.shell.run("bt security 2")
    await wait_both((central, peripheral), r"Security changed: .* level 2")


async def test_pairing_encryption_and_controller_privacy(shell_pair):
    """Bond, then reconnect from RPAs that each Controller must resolve.

    Both Hosts enable privacy and load each other's IRK into the Controller
    resolving list after bonding. On reconnection the Central initiates from a
    Controller-generated RPA and the Peripheral advertises from an RPA; each
    Controller must resolve the peer back to its identity. Directed
    advertising then uses Controller-generated AdvA and TargetA RPAs (Core
    Vol 6, Part B, 6.2.2 and 6.4).
    """
    peripheral, central = shell_pair
    peripheral_identity = await shell_identity(peripheral)
    central_identity = await shell_identity(central)

    # Before bonding the Peripheral cannot resolve the Central's RPA.
    seen = await connect(peripheral, central, address=peripheral_identity)
    assert seen != central_identity
    await central.shell.run("bt security 2")
    await wait_both((central, peripheral), "Bonded with ")
    await central.shell.run("bt security")
    await central.wait_log("BT_SECURITY_L2")
    await disconnect(peripheral, central)

    # Undirected RPA advertising; resolution happens in both Controllers.
    await peripheral.shell.run("bt advertise on")
    await peripheral.wait_log("Advertising started")
    seen = await connect(
        peripheral, central, address=peripheral_identity, advertise=False
    )
    assert seen == central_identity
    await _encrypt_with_stored_key(peripheral, central)
    await disconnect(peripheral, central)

    await peripheral.shell.run("bt advertise off")
    await peripheral.wait_log("Advertising stopped")
    await peripheral.shell.run(
        f"bt adv-create conn-nscan ext-adv directed {central_identity} low dir-rpa"
    )
    await peripheral.wait_log("Created adv id: 0")
    await peripheral.shell.run("bt adv-start")
    await peripheral.wait_log(r"Advertiser\[0\].* set started")
    seen = await connect(
        peripheral, central, address=peripheral_identity, advertise=False
    )
    assert seen == central_identity
    await _encrypt_with_stored_key(peripheral, central)
    await disconnect(peripheral, central)
