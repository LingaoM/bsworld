# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Mesh shell procedures between devices. They pass before and after the fixes."""

from conftest import CID, provision_adv

UUID1 = "11111111111111111111111111111111"
UUID2 = "22222222222222222222222222222222"


async def test_pb_adv_config_and_health(network):
    prov, node1, _ = network
    await provision_adv(prov, node1, UUID1, "0x0002")
    await prov.run(
        "mesh models cfg get-comp", until="Got Composition Data for 0x0002", timeout=15
    )
    await prov.bind("0x0002", "0x0002")
    await prov.run("mesh target dst 0x0001", until="Destination address set")
    await prov.bind("0x0001", "0x0003")
    await prov.run("mesh target dst 0x0002", until="Destination address set")
    await prov.run("mesh target app 0", until="AppIdx set")
    await node1.run("mesh test health-srv add-fault 0x10", settle=0.5)
    await prov.run(
        f"mesh models health fault-get {CID}", until="Fault Count 1", timeout=15
    )


async def test_pb_gatt(network):
    prov, node1, _ = network
    await node1.run(f"mesh prov uuid {UUID1}", until="Device UUID set")
    await node1.run("mesh prov pb-gatt on", until="PB-GATT enabled")
    await prov.run(
        f"mesh prov remote-gatt {UUID1} 0 0x0003 10",
        until="Node provisioned.*0x0003",
        timeout=30,
    )
    await node1.wait("Local node provisioned.*0x0003", timeout=10)


async def test_proxy_client(network):
    prov, node1, _ = network
    await provision_adv(prov, node1, UUID1, "0x0002")
    await prov.run(
        "mesh models cfg gatt-proxy on", until="GATT Proxy is set to 0x01", timeout=15
    )
    await prov.run("mesh proxy connect 0", settle=5.0)
    await prov.run(
        "mesh models cfg get-comp", until="Got Composition Data for 0x0002", timeout=15
    )
    await prov.run("mesh proxy disconnect 0", settle=3.0)


async def test_low_power_node(network):
    prov, node1, node2 = network
    await provision_adv(prov, node1, UUID1, "0x0002")
    await provision_adv(prov, node2, UUID2, "0x0003")
    await prov.run("mesh target dst 0x0002", until="Destination address set")
    await prov.run(
        "mesh models cfg friend on", until="Friend is set to 0x01", timeout=15
    )
    await node2.run("mesh lpn set on", settle=0.5)
    await node2.wait("Friendship \\(as LPN\\) established", timeout=30)
    await node2.run("mesh lpn set off", settle=0.5)
    await node2.wait("Friendship \\(as LPN\\) lost", timeout=10)


async def test_heartbeat(network):
    prov, node1, _ = network
    await provision_adv(prov, node1, UUID1, "0x0002")
    await prov.run("mesh target dst 0x0001", until="Destination address set")
    await prov.run(
        "mesh models cfg hb-sub 0x0002 0x0001 0x10", until="Heartbeat", timeout=10
    )
    await prov.run("mesh target dst 0x0002", until="Destination address set")
    await prov.run(
        "mesh models cfg hb-pub 0x0001 0x05 0x01 7 0 0", until="Heartbeat", timeout=10
    )
    await prov.run("mesh target dst 0x0001", settle=8.0)
    out = await prov.run("mesh models cfg hb-sub", until="MaxHops", timeout=10)
    assert "Source:      0x0002" in out, out


async def test_remote_provisioning(network):
    prov, node1, node2 = network
    await provision_adv(prov, node1, UUID1, "0x0002")
    await node2.run(f"mesh prov uuid {UUID2}", until="Device UUID set")
    await node2.run("mesh prov pb-adv on", until="PB-ADV enabled")
    await prov.run("mesh models rpr scan 5", until="Scan started", timeout=15)
    await prov.wait(f"uuid:   {UUID2}", timeout=20)
    await prov.run(f"mesh models rpr provision-remote {UUID2} 0 0x0004", settle=0.5)
    await node2.wait("Local node provisioned.*0x0004", timeout=40)


async def test_dfu_push(network):
    prov, node1, _ = network
    await provision_adv(prov, node1, UUID1, "0x0002")
    for mid in ("0x1400", "0x1402"):
        await prov.bind("0x0002", mid)
    await prov.run("mesh target dst 0x0001", until="Destination address set")
    for mid in ("0x1401", "0x1403"):
        await prov.bind("0x0001", mid)
    await prov.run("mesh target app 0", until="AppIdx set")
    await prov.run("mesh models dfu slot add 4096 0100000000", until="Slot added")
    await prov.run("mesh models dfu cli target 0x0002 0", until="Added target 0x0002")
    await prov.run("mesh models dfu cli send 0", until="Starting DFU")
    await prov.wait("DFU ended: 0", timeout=300)


async def test_blob_transfer(blob_network):
    prov, node1 = blob_network
    await provision_adv(prov, node1, UUID1, "0x0002")
    await prov.bind("0x0002", "0x1400")
    await prov.run("mesh target dst 0x0001", until="Destination address set")
    await prov.bind("0x0001", "0x1401")
    await prov.run("mesh target app 0", until="AppIdx set")
    await node1.run("mesh models blob srv rx 0x1234", until="Receive BLOB")
    await prov.run("mesh models blob cli target 0x0002", until="Added target")
    await prov.run(
        "mesh models blob cli caps", until="Mesh BLOB: capabilities", timeout=30
    )
    await prov.run(
        "mesh models blob cli tx 0x1234 1000 12 256", until="Sending transfer"
    )
    await prov.wait("Mesh BLOB transfer complete", timeout=120)
    await node1.wait("BLOB completed", timeout=5)
