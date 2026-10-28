# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Cross-Controller LE scenarios driven by one Zephyr shell image.

Each scenario runs unchanged Host commands with the Zephyr Virtual Controller
and BSController in every role pairing. A BSController feature passes only if
it also works against an independently implemented Link Layer, so a shared
misreading of the test specifications by BSController and its protocol tests
cannot pass unnoticed. The pure BSController pairing also runs without a Zephyr
Controller executable.
"""

from __future__ import annotations

import re
from dataclasses import replace

import pytest
from tests.integration.zephyr.shell.devices import add_zephyr_shell, initialize_shell

from bsworld.devices import BSController, ProcessInstance, ZephyrController
from bsworld.interference import StaticAttenuation

_TIMEOUT = 45.0
_PERIPHERAL = "C0:FF:EE:42:00:01"
_CENTRAL = "C0:FF:EE:42:00:02"
_OBSERVER = "C0:FF:EE:42:00:03"
# A 200-octet ATT payload spans several LL Data PDUs at the 27-octet default
# and needs the 251-octet maximum to fit in one PDU.
_PAYLOAD = bytes(range(200))
_BLE_ADVERTISING_CHANNELS_MHZ = (2402.0, 2426.0, 2480.0)
_INTERFERENCE_END_US = 5_000_000


@pytest.fixture
def bsworld_default_controller_type():
    # Each scenario selects both Controllers itself; this replaces the
    # directory-wide single-Controller parametrization.
    return None


@pytest.fixture(
    params=[
        (ZephyrController, ZephyrController),
        (BSController, ZephyrController),
        (ZephyrController, BSController),
        (BSController, BSController),
    ],
    ids=["zephyr-zephyr", "bscontroller-zephyr", "zephyr-bscontroller", "bscontroller"],
)
def roles(request, topo):
    """Controller types for (peripheral, central).

    Scenarios without a connection use the first as the advertiser and the
    second for every scanner.
    """
    if request.param == (BSController, BSController):
        # A pure BSController topology must not depend on a Zephyr executable.
        topo.env = replace(topo.env, hci_virt_bin=None)
        topo.bsim.env = topo.env
    return request.param


async def _start(topo, roles) -> tuple[ProcessInstance, ProcessInstance]:
    peripheral_type, central_type = roles
    peripheral = add_zephyr_shell(
        topo, name="peripheral", address=_PERIPHERAL, controller_type=peripheral_type
    )
    central = add_zephyr_shell(
        topo, name="central", address=_CENTRAL, controller_type=central_type
    )
    topo.set_channel_attenuation(default_db=45.0)
    await _start_shells(topo, peripheral, central)
    return peripheral, central


async def _start_shells(topo, *devices: ProcessInstance) -> None:
    await topo.start()
    for device in devices:
        await initialize_shell(device)


async def _both(devices, pattern: str) -> None:
    for device in devices:
        await device.wait_log(pattern, timeout=_TIMEOUT)


async def _connect(
    peripheral: ProcessInstance,
    central: ProcessInstance,
    *,
    peer_pattern: str = "",
    options: str = "",
) -> None:
    await central.shell.run(f"bt connect P:{_PERIPHERAL} {options}".strip())
    await central.wait_log(rf"Connected: P:{_PERIPHERAL}", timeout=_TIMEOUT)
    await peripheral.wait_log(rf"Connected: {peer_pattern}", timeout=_TIMEOUT)


async def _disconnect(peripheral: ProcessInstance, central: ProcessInstance) -> None:
    await central.shell.run("bt disconnect")
    # Local termination reports 0x16; the peer sees the remote user's 0x13.
    await central.wait_log(r"Disconnected: .*reason 0x16", timeout=_TIMEOUT)
    await peripheral.wait_log(r"Disconnected: .*reason 0x13", timeout=_TIMEOUT)


async def _discover_notify_characteristic(central: ProcessInstance) -> tuple[int, int]:
    await central.shell.run("gatt discover")
    value_handle = ccc_handle = None
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
        elif uuid == "2902" and value_handle is not None and ccc_handle is None:
            ccc_handle = int(handle, 16)
    assert value_handle is not None and ccc_handle is not None
    return value_handle, ccc_handle


def _scan_pattern(advertiser: ProcessInstance) -> str:
    address = advertiser.controller.public_address
    assert address is not None
    return rf"\[DEVICE\]: .*{re.escape(address)}.*RSSI"


async def test_passive_scan_finds_nonconnectable_advertiser(topo, roles):
    """Passive scanning reports legacy non-connectable advertising."""
    advertiser, scanner = await _start(topo, roles)
    await advertiser.shell.run("bt advertise nconn identity")
    await advertiser.wait_log(r"Advertising started", timeout=_TIMEOUT)
    await scanner.shell.run("bt scan passive")
    await scanner.wait_log(_scan_pattern(advertiser), timeout=_TIMEOUT)


async def test_targeted_interference_isolates_and_recovers(topo, roles):
    """CW jammers on the advertising channels block only the exposed scanner.

    The jammers reach one scanner at 0 dB and are isolated from the other, so
    the protected scanner receives the advertiser while the jammed one stays
    silent until the interference window ends.
    """
    advertiser_type, scanner_type = roles
    advertiser = add_zephyr_shell(
        topo, name="advertiser", address=_PERIPHERAL, controller_type=advertiser_type
    )
    protected = add_zephyr_shell(
        topo, name="protected_scanner", address=_CENTRAL, controller_type=scanner_type
    )
    jammed = add_zephyr_shell(
        topo, name="jammed_scanner", address=_OBSERVER, controller_type=scanner_type
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
            StaticAttenuation(tx=advertiser, rx=protected, attenuation_db=45.0),
            StaticAttenuation(tx=advertiser, rx=jammed, attenuation_db=45.0),
            *(
                StaticAttenuation(tx=jammer, rx=protected, attenuation_db=100.0)
                for jammer in jammers
            ),
            *(
                StaticAttenuation(tx=jammer, rx=jammed, attenuation_db=0.0)
                for jammer in jammers
            ),
        ],
    )
    await _start_shells(topo, advertiser, protected, jammed)

    await advertiser.shell.run("bt advertise nconn identity")
    await advertiser.wait_log(r"Advertising started", timeout=_TIMEOUT)
    for scanner in (protected, jammed):
        await scanner.shell.run("bt scan passive")
        await scanner.wait_log(r"Bluetooth passive scan enabled", timeout=_TIMEOUT)
    pattern = _scan_pattern(advertiser)
    await protected.wait_log(pattern, timeout=_TIMEOUT)
    with pytest.raises(TimeoutError):
        await jammed.wait_log(pattern, timeout=2.0)
    await jammed.wait_log(pattern, timeout=_TIMEOUT)


async def test_connection_link_layer_procedures(topo, roles):
    """PHY, data length, connection and channel map updates from either role.

    Every procedure completes when initiated by the side under test, and the
    link still carries a 200-octet notification byte-exactly afterwards.
    """
    peripheral, central = await _start(topo, roles)
    await peripheral.shell.run("gatt register")
    await peripheral.wait_log(r"Registered test vendor service", timeout=_TIMEOUT)
    await peripheral.shell.run("bt advertise on identity")
    await peripheral.wait_log(r"Advertising started", timeout=_TIMEOUT)
    await _connect(peripheral, central)
    devices = (central, peripheral)

    # PHY Update (Core Vol 6, Part B, 5.1.10). The responder answers with the
    # preference of its own last LE Set PHY, so only the Central initiates
    # here; the Peripheral-initiated case runs in the LE Coded scenario.
    for mask, phy in (("4", "LE Coded"), ("2", "LE 2M"), ("1", "LE 1M")):
        await central.shell.run(f"bt phy-update {mask}")
        await _both(devices, rf"LE PHY updated: TX PHY {phy}, RX PHY {phy}")

    # Data Length Update (5.1.9); each side reports its own TX and RX.
    for initiator, responder, octets in (
        (central, peripheral, 251),
        (central, peripheral, 27),
        (peripheral, central, 200),
    ):
        await initiator.shell.run(f"bt data-len-update {octets}")
        await initiator.wait_log(
            rf"LE data len updated: TX \(len: {octets} ", timeout=_TIMEOUT
        )
        await responder.wait_log(
            rf"LE data len updated: .*RX \(len: {octets} ", timeout=_TIMEOUT
        )

    # Connection Update (5.1.1) from the Central and Connection Parameters
    # Request (5.1.7) from the Peripheral. Values are hexadecimal HCI units and
    # differ from both Controllers' initial choices (0x0018 for BSController,
    # 0x0028 for Zephyr): an update that changes nothing is not reported to the
    # Peripheral's Host (Vol 4, Part E, 7.7.65.3).
    await central.shell.run("bt conn-update 0020 0020 0 0190")
    await _both(devices, r"LE conn param updated: int 0x0020 lat 0 to 400")
    await peripheral.shell.run("bt conn-update 0030 0030 1 0190")
    await central.wait_log(
        r"LE conn param req: int \(0x0030, 0x0030\)", timeout=_TIMEOUT
    )
    await _both(devices, r"LE conn param updated: int 0x0030 lat 1 to 400")

    # Channel Map Update (5.1.2) from Host classification: channels 0-7 and
    # 16-23 stay usable. The following ATT traffic must survive the new map.
    await central.shell.run("bt channel-map 0000ff00ff")

    await central.shell.run("gatt exchange-mtu")
    await central.wait_log(r"Exchange successful", timeout=_TIMEOUT)
    value_handle, ccc_handle = await _discover_notify_characteristic(central)
    await central.shell.run(f"gatt subscribe {ccc_handle:x} {value_handle:x}")
    await central.wait_log(r"Subscribed", timeout=_TIMEOUT)
    await central.shell.run(f"gatt read {ccc_handle:x}")
    await central.wait_log(r"Read complete: err 0x00 length 2", timeout=_TIMEOUT)
    # The CCC read on the same ATT bearer confirms notifications are enabled
    # before the server sends, avoiding timing sleeps.
    await central.wait_log(r"01 00", timeout=_TIMEOUT)
    await peripheral.shell.run(f"gatt notify {value_handle:x} {_PAYLOAD.hex()}")
    await central.wait_log(
        rf"Notification: value_handle {value_handle}, length {len(_PAYLOAD)}",
        timeout=_TIMEOUT,
    )
    for row in range(0, len(_PAYLOAD), 16):
        # shell_hexdump separates the two 8-octet halves with two spaces.
        octets = r"\s+".join(f"{value:02x}" for value in _PAYLOAD[row : row + 16])
        await central.wait_log(rf"(?i){row:08x}: {octets}", timeout=_TIMEOUT)
    await _disconnect(peripheral, central)


async def test_pairing_encryption_and_controller_privacy(topo, roles):
    """Bond, then reconnect through Controller address resolution.

    Both Hosts enable privacy and load each other's IRK into the Controller
    resolving list after bonding. On reconnection the Central initiates from a
    Controller-generated RPA (own address type 0x03) and the Peripheral
    advertises from an RPA; each Controller must resolve the peer back to its
    public identity. Directed advertising then uses Controller-generated AdvA
    and TargetA RPAs (Core Vol 6, Part B, 6.2.2 and 6.4).
    """
    peripheral, central = await _start(topo, roles)
    devices = (central, peripheral)
    await peripheral.shell.run("bt advertise on identity")
    await peripheral.wait_log(r"Advertising started", timeout=_TIMEOUT)
    # Before bonding the Peripheral cannot resolve the Central's RPA.
    await _connect(peripheral, central, peer_pattern=r"R:")
    await central.shell.run("bt security 2")
    await _both(devices, r"Bonded with ")
    await central.shell.run("bt security")
    await central.wait_log(r"BT_SECURITY_L2", timeout=_TIMEOUT)
    await _disconnect(peripheral, central)

    # Undirected RPA advertising; resolution happens in both Controllers.
    await peripheral.shell.run("bt advertise on")
    await peripheral.wait_log(r"Advertising started", timeout=_TIMEOUT)
    await _connect(peripheral, central, peer_pattern=rf"P:{_CENTRAL}")
    # Encryption restarts from the stored LTK without pairing again.
    await central.shell.run("bt security 2")
    await _both(devices, r"Security changed: .* level 2")
    await _disconnect(peripheral, central)

    await peripheral.shell.run("bt advertise off")
    await peripheral.wait_log(r"Advertising stopped", timeout=_TIMEOUT)
    await peripheral.shell.run(
        f"bt adv-create conn-nscan ext-adv directed P:{_CENTRAL} low dir-rpa"
    )
    await peripheral.wait_log(r"Created adv id: 0", timeout=_TIMEOUT)
    await peripheral.shell.run("bt adv-start")
    await peripheral.wait_log(r"Advertiser\[0\].* set started", timeout=_TIMEOUT)
    await _connect(peripheral, central, peer_pattern=rf"P:{_CENTRAL}")
    await central.shell.run("bt security 2")
    await _both(devices, r"Security changed: .* level 2")
    await _disconnect(peripheral, central)


async def test_coded_phy_extended_connection(topo, roles):
    """Connect from LE Coded extended advertising without any 1M scanning."""
    peripheral, central = await _start(topo, roles)
    await peripheral.shell.run("bt adv-create conn-nscan ext-adv coded identity")
    await peripheral.wait_log(r"Created adv id: 0", timeout=_TIMEOUT)
    await peripheral.shell.run("bt adv-start")
    await peripheral.wait_log(r"Advertiser\[0\].* set started", timeout=_TIMEOUT)
    await _connect(peripheral, central, options="coded no-1m")
    for device in (central, peripheral):
        await device.shell.run("bt info")
        await device.wait_log(
            r"LE PHY: TX PHY LE Coded, RX PHY LE Coded", timeout=_TIMEOUT
        )
    # Peripheral-initiated PHY Update; the Central has not set a preference.
    await peripheral.shell.run("bt phy-update 2")
    await _both((central, peripheral), r"LE PHY updated: TX PHY LE 2M, RX PHY LE 2M")
    await _disconnect(peripheral, central)


async def test_active_scan_and_filter_accept_list(topo, roles):
    """Active scanning returns scan response data; FAL initiation connects."""
    peripheral, central = await _start(topo, roles)
    # Legacy connectable advertising carries the device name in SCAN_RSP.
    await peripheral.shell.run("bt advertise on identity")
    await peripheral.wait_log(r"Advertising started", timeout=_TIMEOUT)
    await central.shell.run("bt scan on")
    await central.wait_log(r"Bluetooth active scan enabled", timeout=_TIMEOUT)
    await central.wait_log(
        rf"\[DEVICE\]: P:{_PERIPHERAL}, AD evt type 4, "
        r".*BSWorld shell C:1 S:1 D:0 SR:1",
        timeout=_TIMEOUT,
    )
    await central.shell.run("bt scan off")
    await central.wait_log(r"Scan successfully stopped", timeout=_TIMEOUT)

    await central.shell.run(f"bt fal-add P:{_PERIPHERAL}")
    await central.shell.run("bt fal-connect on")
    await central.wait_log(rf"Connected: P:{_PERIPHERAL}", timeout=_TIMEOUT)
    await peripheral.wait_log(r"Connected: ", timeout=_TIMEOUT)
    await _disconnect(peripheral, central)


async def test_periodic_advertising_sync_recovers(topo, roles):
    """Synchronize to a periodic train, lose it, and synchronize again.

    Stopping the train must end the sync; restarting it with new data must
    allow a second sync that reports the new payload.
    """
    advertiser, observer = await _start(topo, roles)
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
        rf"\[DEVICE\]: P:{_PERIPHERAL},.*Interval: 0x0050.*SID: 0x", timeout=_TIMEOUT
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
    await advertiser.shell.run_many(("bt per-adv-data 03ff425357", "bt per-adv on"))
    await advertiser.wait_log(r"Periodic advertising started", timeout=_TIMEOUT)
    await observer.shell.run(create_sync)
    await observer.wait_log(r"PER_ADV_SYNC\[\d+\]: .* synced", timeout=_TIMEOUT)
    await observer.wait_log(r"PER_ADV_SYNC\[\d+\]: .*data length 5", timeout=_TIMEOUT)
