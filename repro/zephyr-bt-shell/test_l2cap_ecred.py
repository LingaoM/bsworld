# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""l2cap ecred-reconfigure without an MTU (issue B).

The command is registered with the MTU as optional, but the handler always
parses argv[1]. Without an MTU it passes NULL to shell_strtoul() and the
process crashes with SIGSEGV.
"""

from conftest import connect


async def test_ecred_reconfigure_without_mtu(pair):
    periph, central = pair
    await connect(periph, central)
    await periph.run("l2cap register 29", until="registered")
    await central.run("l2cap ecred-connect 29", until=r"Channel \S+ connected")

    await central.run("l2cap ecred-reconfigure", until="wrong parameter count")
    # The shell still runs and accepts an MTU. The channel's receive MTU is
    # 230 (DATA_MTU in l2cap.c), and a reconfiguration may not decrease it.
    await central.run(
        "l2cap ecred-reconfigure 230", until="L2CAP reconfiguration pending"
    )
