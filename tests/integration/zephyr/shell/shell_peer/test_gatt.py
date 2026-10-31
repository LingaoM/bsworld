# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

from tests.integration.zephyr.shell.shell_peer.common import (
    connect,
    disconnect,
    notify_and_verify,
    wait_both,
)


async def test_encrypted_gatt(shell_pair):
    peripheral, central = shell_pair
    await peripheral.shell.run("gatt register")
    await peripheral.wait_log("Registered test vendor service")
    await connect(peripheral, central)
    await central.shell.run("bt security 2")
    await wait_both((central, peripheral), r"Security changed: .* level 2")
    await notify_and_verify(peripheral, central, b"BSWorld")
    await disconnect(peripheral, central)
