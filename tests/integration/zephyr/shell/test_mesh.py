# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Mesh provisioning and model control driven by the upstream Mesh shell.

Every node runs the same Controller type, selected by the directory-wide
Controller parametrization.
"""

from __future__ import annotations

import asyncio
import re

from tests.integration.zephyr.shell.devices import (
    add_zephyr_shell,
    initialize_shell,
)

from bsworld.devices import ProcessInstance

_TIMEOUT = 45.0


async def _start_shells(topo, *devices: ProcessInstance) -> None:
    await topo.start()
    async with asyncio.TaskGroup() as tasks:
        for device in devices:
            tasks.create_task(initialize_shell(device, mesh=True))


async def _initialize_provisioner(provisioner: ProcessInstance) -> None:
    await provisioner.shell.run_many(
        (
            "mesh cdb create 000102030405060708090a0b0c0d0e0f",
            "mesh prov local 0 0x0001",
            "mesh prov beacon-listen on",
            "mesh prov auth-method none",
        )
    )
    await provisioner.wait_log(
        r"Local node provisioned, net_idx 0x0000 address 0x0001", timeout=_TIMEOUT
    )


async def _provision_node(
    provisioner: ProcessInstance, node: ProcessInstance, address: int
) -> None:
    uuid = f"dddd{address:028x}"
    await node.shell.run(f"mesh prov uuid {uuid}")
    await node.wait_log(r"Device UUID set", timeout=_TIMEOUT)
    await node.shell.run("mesh prov pb-adv on")
    await node.wait_log(r"PB-ADV enabled", timeout=_TIMEOUT)
    await provisioner.wait_log(rf"PB-ADV UUID {uuid}", timeout=_TIMEOUT)
    # Disable provisioning attention so only the later application command
    # can produce an Attention On callback in the group-control scenario.
    await provisioner.shell.run(f"mesh prov remote-adv {uuid} 0 {address:#06x} 0")
    await provisioner.wait_log(
        rf"Node provisioned, net_idx 0x0000 address {address:#06x} elements 1",
        timeout=180.0,
    )
    await node.wait_log(
        rf"Local node provisioned, net_idx 0x0000 address {address:#06x}",
        timeout=_TIMEOUT,
    )


async def _bind_app_key(
    provisioner: ProcessInstance, address: int, model_id: int
) -> None:
    await provisioner.shell.run_many(
        (f"mesh target dst {address:#06x}", "mesh models cfg appkey add 0 0")
    )
    await provisioner.wait_log(
        r"AppKey added, NetKeyIndex 0x0000 AppKeyIndex 0x0000", timeout=_TIMEOUT
    )
    await provisioner.shell.run(
        f"mesh models cfg model app-bind {address:#06x} 0 {model_id:#06x}"
    )
    await provisioner.wait_log(r"AppKey successfully bound", timeout=_TIMEOUT)


async def test_provisioning_and_model_control(topo):
    provisioner = add_zephyr_shell(
        topo, name="provisioner", address="C0:FF:EE:41:03:01", mesh=True
    )
    node = add_zephyr_shell(
        topo, name="mesh_node", address="C0:FF:EE:41:03:02", mesh=True
    )
    topo.set_channel_attenuation(default_db=45.0)
    await _start_shells(topo, provisioner, node)
    await _initialize_provisioner(provisioner)
    await _provision_node(provisioner, node, 0x0002)

    await provisioner.shell.run_many(
        ("mesh target dst 0x0002", "mesh models cfg get-comp")
    )
    await provisioner.wait_log(r"Got Composition Data for 0x0002", timeout=_TIMEOUT)
    line = await provisioner.wait_log(r"CID\s+0x[0-9a-fA-F]+", timeout=_TIMEOUT)
    match = re.search(r"CID\s+(0x[0-9a-fA-F]+)", line)
    assert match is not None
    company_id = match[1]

    # Provisioning gives the nodes their DeviceKeys. Configure a shared AppKey
    # and bind the upstream Health models so the final request also exercises
    # application-key encryption, rather than stopping at configuration logs.
    await _bind_app_key(provisioner, 0x0002, 0x0002)
    await provisioner.shell.run("mesh models cfg ttl 5")
    await provisioner.wait_log(r"Default TTL is 0x05", timeout=_TIMEOUT)
    await provisioner.shell.run("mesh models cfg ttl")
    await provisioner.wait_log(r"Default TTL is 0x05", timeout=_TIMEOUT)

    await _bind_app_key(provisioner, 0x0001, 0x0003)
    await provisioner.shell.run_many(
        (
            "mesh target dst 0x0002",
            "mesh target app 0",
            f"mesh models health fault-get {company_id}",
        )
    )
    await node.wait_log(r"Sending registered faults", timeout=_TIMEOUT)
    await provisioner.wait_log(
        rf"Health Test ID 0x00 Company ID {company_id}: no faults", timeout=_TIMEOUT
    )


async def test_group_controls_subscribed_nodes(topo):
    provisioner = add_zephyr_shell(
        topo, name="provisioner", address="C0:FF:EE:41:04:01", mesh=True
    )
    nodes = [
        add_zephyr_shell(
            topo,
            name=f"mesh_node_{address}",
            address=f"C0:FF:EE:41:04:{address:02X}",
            mesh=True,
        )
        for address in range(2, 5)
    ]
    topo.set_channel_attenuation(default_db=45.0)
    await _start_shells(topo, provisioner, *nodes)
    await _initialize_provisioner(provisioner)
    for address, node in enumerate(nodes, start=2):
        await _provision_node(provisioner, node, address)
        await _bind_app_key(provisioner, address, 0x0002)
        if address in (2, 3):
            await provisioner.shell.run(
                f"mesh models cfg model sub-add {address:#06x} 0xc000 0x0002"
            )
            await provisioner.wait_log(
                r"Model subscription was successful", timeout=_TIMEOUT
            )
    await _bind_app_key(provisioner, 0x0001, 0x0003)

    # Mesh Protocol v1.1 Sections 3.7.4.1 and 4.4.3.1 define group updates
    # and Health Server subscriptions. The upstream shell exposes Attention
    # callbacks, so verify that each subscribed server receives the command.
    await provisioner.shell.run_many(
        (
            "mesh target dst 0xc000",
            "mesh target app 0",
            "mesh models health attention-set-unack 120",
        )
    )
    async with asyncio.timeout(5.0):
        for member in nodes[:2]:
            await member.wait_log(r"Attention On", timeout=_TIMEOUT)
        # The third node shares the AppKey and can answer Health requests, but
        # has no group subscription. Read its state to verify isolation without
        # treating silence or a missing key as proof that filtering worked.
        await provisioner.shell.run_many(
            ("mesh target dst 0x0004", "mesh models health attention-get")
        )
        await provisioner.wait_log(
            r"Health Attention Status from 0x0004: 0\b", timeout=_TIMEOUT
        )
        await provisioner.wait_log(r"Health Attention Timer: 0\b", timeout=_TIMEOUT)

    await provisioner.shell.run_many(
        ("mesh target dst 0xc000", "mesh models health attention-set-unack 0")
    )
    # Require the Off callbacks well before the 120-second timer expires, so
    # natural expiration cannot be mistaken for receipt of the group command.
    async with asyncio.timeout(5.0):
        for member in nodes[:2]:
            await member.wait_log(r"Attention Off", timeout=_TIMEOUT)
