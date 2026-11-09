# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Mesh shell documentation that does not match the shell (PR MF).

These tests pass before and after the documentation fix. Each one runs the
documented form next to the form the shell accepts.
"""

import re

from conftest import DEFAULT_KEY


async def test_prov_local_needs_cdb(single):
    # Basic usage: "mesh prov local 0 0x0001". The application enables the CDB.
    await single.run("mesh prov local 0 0x0001", until="No cdb entry for subnet")
    await single.run(f"mesh cdb create {DEFAULT_KEY}", settle=0.5)
    await single.run("mesh prov local 0 0x0001", until="Local node provisioned")


async def test_cdb_create_key(single):
    # Documented: "Defaults to the default key value if omitted."
    await single.run("mesh cdb create", settle=0.5)
    out = await single.run("mesh cdb show", until="Total subnets")
    key = re.search(r"0x000\s+([0-9a-f]{32})", out)[1]
    assert key != DEFAULT_KEY, out


async def test_boolean_values(node):
    # Documented: enabled, disabled. The shell accepts enable, disable.
    await node.run("mesh models cfg beacon enabled", until="Unable to parse")
    await node.run(
        "mesh models cfg beacon enable", until="Beacon state is 0x01", timeout=10
    )


async def test_health_fault_id_size(single):
    # Documented range: 0x0001 to 0xFFFF. The fault ID is 8 bits.
    await single.run("mesh test health-srv add-fault 0x0100", until="must be non-zero")


async def test_auth_method_output_action_0(single):
    # Documented: "0 - No output action".
    await single.run("mesh prov auth-method output 0 4", until="failed \\(err -22\\)")


async def test_removed_command_names(single):
    for command, error in (
        ("mesh models cfg target get", "wrong parameter count"),
        ("mesh models cfg help", "unknown command: help"),
        ("mesh models rpr instance-get-all", "unknown command: instance-get-all"),
        ("mesh models od_priv_proxy od-priv-gatt-proxy", "unknown command"),
        ("mesh models sol_pdu_rpl sol-pdu-rpl-clear 1 0", "wrong parameter count"),
        ("mesh provision 0 1", "wrong parameter count"),
    ):
        await single.run(command, until=error)


async def test_current_command_names(node):
    await node.run("mesh models rpr instance get-all", until="instance found")
    await node.run(
        "mesh models od_priv_proxy gatt-proxy",
        until="On-Demand Private GATT Proxy",
        timeout=10,
    )
    await node.run("mesh models sol_pdu_rpl clear 0x0001 0", settle=1.0)
