# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Mesh shell commands that crash the device (issue MC).

Each test runs a command that crashes the shell with SIGSEGV before the fix
and checks the correct result.
"""

from conftest import provision_adv


async def test_rpr_link_close_first(node):
    # link-close is the first Remote Provisioning Client command after boot,
    # so the shell has not looked up the client model yet.
    await node.run(
        "mesh models rpr link-close",
        until="Remote Provisioning Link on|failed",
        timeout=15,
    )


async def test_cfg_model_pub_seven_parameters(node):
    # Int(ms), the eighth publication parameter, is missing.
    await node.run(
        "mesh models cfg model pub 0x0001 0x0002 0xc000 0 off 7 0 0 2",
        until="Invalid number of argument",
    )


async def test_dfu_metadata_encode_user_data(single):
    await single.run(
        "mesh models dfu metadata encode 1 0 0 0 1000 1 0x12345678 1 abcd",
        until="User data length",
    )
    await single.wait("User data: abcd")


async def _dfu_pair(network):
    prov, node1, _ = network
    await provision_adv(prov, node1, "11111111111111111111111111111111", "0x0002")
    # BLOB Transfer Server 0x1400 and Firmware Update Server 0x1402 on the node,
    # BLOB Transfer Client 0x1401 and Firmware Update Client 0x1403 locally.
    for mid in ("0x1400", "0x1402"):
        await prov.bind("0x0002", mid)
    await prov.run("mesh target dst 0x0001", until="Destination address set")
    for mid in ("0x1401", "0x1403"):
        await prov.bind("0x0001", mid)
    await prov.run("mesh target app 0", until="AppIdx set")
    return prov, node1


async def test_dfu_pull_after_target(network):
    prov, _ = await _dfu_pair(network)
    # Pull mode is slow, so keep the image small enough to finish before the
    # default BLOB timeout of 20 s.
    await prov.run("mesh models dfu slot add 512 0100000000", until="Slot added")
    await prov.run("mesh models dfu cli target 0x0002 0", until="Added target 0x0002")
    out = await prov.run(
        "mesh models dfu cli send 0 0 pull", until="Starting DFU|Unable to parse"
    )
    if "Unable to parse" in out:
        # Without the mode parsing fix (issue MD), the mode is a number: 2 is pull.
        await prov.run("mesh models dfu cli send 0 0 2", until="Starting DFU")
    await prov.wait("DFU ended: 0", timeout=300)


async def test_blob_cli_with_dfu_client(network):
    prov, _ = await _dfu_pair(network)
    # This image has a Firmware Update Client, whose BLOB Transfer Client the
    # BLOB commands must not drive.
    await prov.run("mesh models blob cli target 0x0002", until="Added target 0x0002")
    await prov.run(
        "mesh models blob cli caps",
        until="in use by another model|Retrieving transfer capabilities",
    )
    await prov.wait("BLOB Transfer Client is in use by another model", timeout=1)
    await prov.run("mesh target dst 0x0001", settle=10.0)
    assert prov.alive()
