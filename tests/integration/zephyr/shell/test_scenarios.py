# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Command-driven Zephyr Host scenarios using upstream shell executables."""

from __future__ import annotations

import asyncio
import re

import pytest
from tests.integration.zephyr.shell.devices import (
    add_zephyr_shell,
    initialize_shell,
)

from bsworld.devices import ProcessInstance
from bsworld.interference import StaticAttenuation

_TIMEOUT = 45.0
_BLE_ADVERTISING_CHANNELS_MHZ = (2402.0, 2426.0, 2480.0)
_INTERFERENCE_END_US = 5_000_000


async def _start_shells(topo, *devices: ProcessInstance, mesh: bool = False) -> None:
    await topo.start()
    async with asyncio.TaskGroup() as tasks:
        for device in devices:
            tasks.create_task(initialize_shell(device, mesh=mesh))


def _scan_pattern(advertiser: ProcessInstance) -> str:
    address = advertiser.controller.public_address
    assert address is not None
    return rf"\[DEVICE\]: .*{re.escape(address)}.*RSSI"


async def test_zephyr_shell_scanner_finds_advertiser(topo):
    advertiser = add_zephyr_shell(topo, name="advertiser", address="C0:FF:EE:41:00:01")
    scanner = add_zephyr_shell(topo, name="scanner", address="C0:FF:EE:41:00:02")
    topo.set_channel_attenuation(default_db=45.0)
    await _start_shells(topo, advertiser, scanner)

    await advertiser.shell.run("bt advertise nconn identity")
    await advertiser.wait_log(r"Advertising started", timeout=_TIMEOUT)
    await scanner.shell.run("bt scan passive")
    await scanner.wait_log(_scan_pattern(advertiser), timeout=_TIMEOUT)


async def test_zephyr_shell_targeted_interference_isolates_and_recovers(topo):
    advertiser = add_zephyr_shell(topo, name="advertiser", address="C0:FF:EE:41:00:01")
    protected_scanner = add_zephyr_shell(
        topo, name="protected_scanner", address="C0:FF:EE:41:00:02"
    )
    jammed_scanner = add_zephyr_shell(
        topo, name="jammed_scanner", address="C0:FF:EE:41:00:03"
    )
    jammers = [
        topo.add_burst_interference(
            frequency_mhz,
            power_dbm=20.0,
            interf_type="CW",
            windows=[(1, _INTERFERENCE_END_US)],
        )
        for frequency_mhz in _BLE_ADVERTISING_CHANNELS_MHZ
    ]
    topo.set_channel_attenuation(
        default_db=100.0,
        static_paths=[
            StaticAttenuation(tx=advertiser, rx=protected_scanner, attenuation_db=45.0),
            StaticAttenuation(tx=advertiser, rx=jammed_scanner, attenuation_db=45.0),
            *(
                StaticAttenuation(tx=jammer, rx=protected_scanner, attenuation_db=100.0)
                for jammer in jammers
            ),
            *(
                StaticAttenuation(tx=jammer, rx=jammed_scanner, attenuation_db=0.0)
                for jammer in jammers
            ),
        ],
    )
    await _start_shells(topo, advertiser, protected_scanner, jammed_scanner)

    await advertiser.shell.run("bt advertise nconn identity")
    await advertiser.wait_log(r"Advertising started", timeout=_TIMEOUT)
    await protected_scanner.shell.run("bt scan passive")
    await jammed_scanner.shell.run("bt scan passive")
    await protected_scanner.wait_log(
        r"Bluetooth passive scan enabled", timeout=_TIMEOUT
    )
    await jammed_scanner.wait_log(r"Bluetooth passive scan enabled", timeout=_TIMEOUT)
    pattern = _scan_pattern(advertiser)
    await protected_scanner.wait_log(pattern, timeout=_TIMEOUT)
    with pytest.raises(TimeoutError):
        await jammed_scanner.wait_log(pattern, timeout=2.0)
    await jammed_scanner.wait_log(pattern, timeout=_TIMEOUT)


async def test_zephyr_shell_gatt_discovery_and_notifications(topo):
    peripheral = add_zephyr_shell(topo, name="peripheral", address="C0:FF:EE:41:01:01")
    central = add_zephyr_shell(topo, name="central", address="C0:FF:EE:41:01:02")
    topo.set_channel_attenuation(default_db=45.0)
    await _start_shells(topo, peripheral, central)

    # Reuse the upstream GATT shell's test service, including its notify value
    # and CCC descriptor, rather than maintaining a separate application loop.
    await peripheral.shell.run("gatt register")
    await peripheral.wait_log(
        r"Registered test vendor service .*56789abcdef4", timeout=_TIMEOUT
    )
    await peripheral.shell.run("bt advertise on identity")
    await peripheral.wait_log(r"Advertising started", timeout=_TIMEOUT)
    await central.shell.run("bt connect P:C0:FF:EE:41:01:01")
    await central.wait_log(r"Connected: .*C0:FF:EE:41:01:01", timeout=_TIMEOUT)
    await peripheral.wait_log(r"Connected: .*C0:FF:EE:41:01:02", timeout=_TIMEOUT)

    await central.shell.run("gatt discover")
    value_handle = None
    ccc_handle = None
    while True:
        line = await central.wait_log(
            r"Descriptor .* found: handle|Discover complete", timeout=_TIMEOUT
        )
        if "Discover complete" in line:
            break
        match = re.search(r"Descriptor (\S+) found: handle ([0-9a-f]+)", line)
        assert match is not None
        uuid, handle = match.groups()
        if uuid.endswith("56789abcdef5"):
            value_handle = int(handle, 16)
        elif uuid == "2902" and value_handle is not None:
            ccc_handle = int(handle, 16)
    assert value_handle is not None, "upstream notify characteristic was not discovered"
    assert ccc_handle is not None, "notify characteristic has no CCC descriptor"

    await central.shell.run(f"gatt subscribe {ccc_handle:x} {value_handle:x}")
    await central.wait_log(r"Subscribed", timeout=_TIMEOUT)
    # Subscribed reports that the asynchronous CCC write was queued. A read on
    # the same ATT bearer confirms the peer has enabled notifications before
    # the server sends the value, avoiding timing sleeps in the scenario.
    await central.shell.run(f"gatt read {ccc_handle:x}")
    await central.wait_log(r"Read complete: err 0x00 length 2", timeout=_TIMEOUT)
    await central.wait_log(r"01 00", timeout=_TIMEOUT)
    await peripheral.shell.run(f"gatt notify {value_handle:x} 4253576f726c64")
    await central.wait_log(
        rf"Notification: value_handle {value_handle}, length 7", timeout=_TIMEOUT
    )
    await central.wait_log(r"42 53 57 6[fF] 72 6[cC] 64", timeout=_TIMEOUT)


async def test_zephyr_shell_periodic_advertising_sync_recovers(topo):
    advertiser = add_zephyr_shell(
        topo, name="periodic_advertiser", address="C0:FF:EE:41:02:01"
    )
    observer = add_zephyr_shell(
        topo, name="periodic_observer", address="C0:FF:EE:41:02:02"
    )
    topo.set_channel_attenuation(default_db=45.0)
    await _start_shells(topo, advertiser, observer)

    await advertiser.shell.run("bt adv-create nconn-nscan ext-adv identity")
    await advertiser.wait_log(r"Created adv id: 0", timeout=_TIMEOUT)
    # Interval arguments are hexadecimal multiples of 1.25 ms. The data
    # command takes a payload length, AD type, then the payload bytes.
    await advertiser.shell.run_many(
        (
            "bt per-adv-param 0050 0050",
            "bt per-adv-data 02ff4253",
            "bt per-adv on",
            "bt adv-start",
        )
    )
    await advertiser.wait_log(r"Periodic advertising started", timeout=_TIMEOUT)
    await advertiser.wait_log(r"Advertiser\[0\].* set started", timeout=_TIMEOUT)
    await observer.shell.run("bt scan passive")
    line = await observer.wait_log(
        r"\[DEVICE\]: .*C0:FF:EE:41:02:01.*Interval: 0x0050.*SID: 0x",
        timeout=_TIMEOUT,
    )
    match = re.search(r"\[DEVICE\]: ([PR]:[^,]+).*SID: 0x([0-9a-f]+)", line)
    assert match is not None
    address, sid = match.groups()
    # This shell parses timeout in hexadecimal HCI units of 10 ms, despite
    # its help labelling the argument as ms: 0x00c8 means two seconds.
    create_sync = f"bt per-adv-sync-create {address} {sid} skip 0 timeout 00c8"
    await observer.shell.run(create_sync)
    await observer.wait_log(r"PER_ADV_SYNC\[\d+\]: .* synced", timeout=_TIMEOUT)
    await observer.wait_log(r"PER_ADV_SYNC\[\d+\]: .*data length 4", timeout=_TIMEOUT)

    await advertiser.shell.run("bt per-adv off")
    await advertiser.wait_log(r"Periodic advertising stopped", timeout=_TIMEOUT)
    await observer.wait_log(r"PER_ADV_SYNC\[\d+\]: .*sync terminated", timeout=_TIMEOUT)
    # Start the next session with new data so recovery also verifies that a
    # command can update the payload without rebuilding the application.
    await advertiser.shell.run_many(("bt per-adv-data 03ff425357", "bt per-adv on"))
    await advertiser.wait_log(r"Periodic advertising started", timeout=_TIMEOUT)
    await observer.shell.run(create_sync)
    await observer.wait_log(r"PER_ADV_SYNC\[\d+\]: .* synced", timeout=_TIMEOUT)
    await observer.wait_log(r"PER_ADV_SYNC\[\d+\]: .*data length 5", timeout=_TIMEOUT)


async def _initialize_mesh_provisioner(provisioner: ProcessInstance) -> None:
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


async def _provision_mesh_node(
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


async def _bind_mesh_app_key(
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


async def test_zephyr_shell_mesh_provisioning_and_model_control(topo):
    provisioner = add_zephyr_shell(
        topo, name="provisioner", address="C0:FF:EE:41:03:01", mesh=True
    )
    node = add_zephyr_shell(
        topo, name="mesh_node", address="C0:FF:EE:41:03:02", mesh=True
    )
    topo.set_channel_attenuation(default_db=45.0)
    await _start_shells(topo, provisioner, node, mesh=True)
    await _initialize_mesh_provisioner(provisioner)
    await _provision_mesh_node(provisioner, node, 0x0002)

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
    await _bind_mesh_app_key(provisioner, 0x0002, 0x0002)
    await provisioner.shell.run("mesh models cfg ttl 5")
    await provisioner.wait_log(r"Default TTL is 0x05", timeout=_TIMEOUT)
    await provisioner.shell.run("mesh models cfg ttl")
    await provisioner.wait_log(r"Default TTL is 0x05", timeout=_TIMEOUT)

    await _bind_mesh_app_key(provisioner, 0x0001, 0x0003)
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


async def test_zephyr_shell_mesh_group_controls_subscribed_nodes(topo):
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
    await _start_shells(topo, provisioner, *nodes, mesh=True)
    await _initialize_mesh_provisioner(provisioner)
    for address, node in enumerate(nodes, start=2):
        await _provision_mesh_node(provisioner, node, address)
        await _bind_mesh_app_key(provisioner, address, 0x0002)
        if address in (2, 3):
            await provisioner.shell.run(
                f"mesh models cfg model sub-add {address:#06x} 0xc000 0x0002"
            )
            await provisioner.wait_log(
                r"Model subscription was successful", timeout=_TIMEOUT
            )
    await _bind_mesh_app_key(provisioner, 0x0001, 0x0003)

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
