# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Mesh shell commands that parse or check their arguments wrongly (#125084)."""

import re

from conftest import provision_adv

LABEL = "00112233445566778899aabbccddeeff"


async def test_prov_static_oob_clear(single):
    await single.run(f"mesh prov static-oob {LABEL}", until="Static OOB value set")
    await single.run(
        "mesh prov static-oob", until="Static OOB value cleared|wrong parameter count"
    )
    await single.wait("Static OOB value cleared", timeout=1)


async def test_cfg_model_pub_va_sig_model(node):
    # Health Server (0x0002) is a SIG model, so no CID follows the model ID.
    await node.bind("0x0001", "0x0002")
    out = await node.run(
        f"mesh models cfg model pub-va 0x0001 {LABEL} 0 off 7 0 0 0 50 0x0002",
        until="Model Publication",
        timeout=10,
    )
    assert "Model Publication successfully set" in out, out


async def test_cfg_model_pub_retransmit_interval(node):
    await node.bind("0x0001", "0x0002")
    # (steps + 1) * 50 ms: 1600 ms is valid, 0 is not.
    out = await node.run(
        "mesh models cfg model pub 0x0001 0x0002 0xc000 0 off 7 0 0 2 1600",
        until="Model Publication|Invalid",
        timeout=10,
    )
    assert "Model Publication successfully set" in out, out
    out = await node.run(
        "mesh models cfg model pub 0x0001 0x0002 0xc000 0 off 7 0 0 2 0",
        until="Model Publication|Invalid",
        timeout=10,
    )
    assert "Invalid retransmit interval" in out, out


async def test_cfg_net_transmit_interval(node):
    out = await node.run(
        "mesh models cfg net-transmit-param 2 320",
        until="Transmit 0x|Invalid",
        timeout=10,
    )
    assert "count 2 interval 320ms" in out, out
    out = await node.run(
        "mesh models cfg net-transmit-param 8 20",
        until="Transmit 0x|Invalid",
        timeout=10,
    )
    assert "Invalid retransmit count" in out, out


async def test_cfg_relay_interval(node):
    out = await node.run(
        "mesh models cfg relay on 3 320", until="Relay is|Invalid", timeout=10
    )
    assert "count 3 interval 320ms" in out, out


async def test_sar_rx_set_argument_order(node):
    # <SegThresh> <AckDelayInc> <DiscardTimeout> <RxSegIntStep> <AckRetransCount>
    await node.run("mesh models sar rx-set 3 1 5 2 0", until="Receiver Set", timeout=10)
    out = await node.run(
        "mesh models sar rx-get", until="Receiver Get: [\\d ]+\\d", timeout=10
    )
    values = re.search(r"Receiver Get: ([\d ]+)", out)[1].split()
    assert values == ["3", "1", "5", "2", "0"], out


async def test_dfu_cli_send_mode_word(single):
    # The help shows <Mode(push, pull)>. There is no target, so the handler
    # stops at that check once the arguments are parsed.
    out = await single.run(
        "mesh models dfu cli send 0 0 pull", until="No targets|Unable to parse"
    )
    assert "No targets" in out, out


async def test_rpr_reprovision_remote_lowest_address(network):
    prov, node1, _ = network
    await provision_adv(prov, node1, "11111111111111111111111111111111", "0x0002")
    # 0 picks the lowest unicast address that is free in the CDB: 0x0001 is
    # the provisioner and 0x0002 the node, so the node moves to 0x0003.
    await prov.run("mesh models rpr reprovision-remote 0", settle=0.5)
    await node1.wait("re-provisioned, new address 0x0003", timeout=60)
