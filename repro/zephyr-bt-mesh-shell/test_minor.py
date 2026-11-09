# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Smaller Mesh shell problems: parse errors, 64-bit BLOB IDs, help texts (#125089)."""


async def test_prb_priv_node_id_get_parse_error(node):
    out = await node.run(
        "mesh models prb priv-node-id-get xyz",
        until="Unable to parse|state",
        timeout=10,
    )
    assert "Unable to parse" in out, out


async def test_blob_cli_tx_get_parse_error(blob_single):
    await blob_single.run("mesh models blob cli target 0x0002", until="Added target")
    out = await blob_single.run("mesh models blob cli tx-get foo", settle=1.0)
    assert "Unable to parse" in out, out


async def test_blob_srv_rx_64bit_id(blob_single):
    out = await blob_single.run(
        "mesh models blob srv rx 0x1122334455667788",
        until="Receive BLOB|Unable to parse",
    )
    assert "Receive BLOB 0x1122334455667788" in out, out


async def test_rpr_scan_srv_needs_ad_type(node):
    # bt_mesh_rpr_scan_start_ext() needs at least one AD type.
    out = await node.run(
        "mesh models rpr scan-srv", until="wrong parameter count|Scan start", timeout=10
    )
    assert "wrong parameter count" in out, out


async def test_auth_method_hexadecimal(single):
    out = await single.run("mesh prov auth-method output 0x8 4", settle=0.5)
    assert "Unable to parse" not in out and "failed" not in out, out


async def test_help_texts(single):
    out = " ".join(
        (await single.run("mesh models prb priv-gatt-proxy-set", settle=0.5)).split()
    )
    assert "priv-gatt-proxy-set - <Val(off, on)>" in out, out
    out = " ".join((await single.run("mesh models cfg node-id", settle=0.5)).split())
    assert "<NetKeyIdx> [Identity]" in out, out
    out = " ".join(
        (await single.run("mesh prov auth-method static", settle=0.5)).split()
    )
    assert "<Val(1-32 hex)>" in out, out
