# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""iso cig_create argument positions (issue C).

The help lists [dir] [C to P interval] [P to C interval] [packing] [framing]
[C to P latency] [P to C latency] [sdu] [phy] [rtn], but the handler reads
the SDU from argv[7] (the P to C latency), the PHY from the SDU argument and
the RTN from the PHY argument.
"""

from conftest import connect


async def test_cig_create_reads_sdu_phy_and_rtn(pair):
    periph, central = pair
    await connect(periph, central)
    # SDU 100, PHY 2 (2M), RTN 2. Before the fix, the PHY is read from the
    # SDU argument and the command fails with "Invalid phy 100".
    await central.run(
        "iso cig_create tx 10000 10000 0 0 10 20 100 2 2",
        until="CIG created|Invalid|Unable",
    )
    await central.wait("CIG created")
    await periph.run("iso listen rx")
    await central.run("iso connect", until=r"ISO Channel \S+ connected", timeout=10)

    # The CIS uses the SDU size from the command.
    await central.run("iso send", until=r"send: 100 bytes of data")
    await periph.wait(r"Incoming data channel \S+ len 100\b", timeout=10)
