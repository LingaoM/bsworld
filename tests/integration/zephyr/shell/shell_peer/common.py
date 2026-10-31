# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Connection and GATT commands shared by shell peer scenarios."""

import re

from tests.integration.zephyr.shell_common import shell_identity

# A 200-octet ATT payload spans several LL Data PDUs at the 27-octet default
# and needs the 251-octet maximum to fit in one PDU.
PAYLOAD = bytes(range(200))


async def wait_both(devices, pattern: str) -> None:
    for device in devices:
        await device.wait_log(pattern)


async def connect(peripheral, central, *, address=None, options="", advertise=True):
    """Connect the Central to the Peripheral and return the Peripheral's view.

    address defaults to the Peripheral's identity. With advertise=False the
    caller has already started the advertiser it wants to test. The returned
    address is the Central as reported by the Peripheral's Host, which shows
    whether its Controller resolved a private address.
    """
    if address is None:
        address = await shell_identity(peripheral)
    if advertise:
        await peripheral.shell.run("bt advertise on identity")
        await peripheral.wait_log("Advertising started")
    await central.shell.run(f"bt connect {address} {options}".strip())
    await central.wait_log(rf"Connected: {re.escape(address)}")
    line = await peripheral.wait_log(r"Connected: [PR]:[0-9A-F:]+")
    return re.search(r"Connected: ([PR]:[0-9A-F:]+)", line)[1]


async def disconnect(peripheral, central):
    await central.shell.run("bt disconnect")
    # Local termination reports 0x16; the peer sees the remote user's 0x13.
    await central.wait_log(r"Disconnected: .*reason 0x16")
    await peripheral.wait_log(r"Disconnected: .*reason 0x13")


async def discover_notify_characteristic(central) -> tuple[int, int]:
    """Return the value and CCC handles of the shell's test vendor service."""
    await central.shell.run("gatt discover")
    value_handle = ccc_handle = None
    while True:
        line = await central.wait_log(r"Descriptor .* found: handle|Discover complete")
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


async def notify_and_verify(peripheral, central, payload: bytes) -> None:
    """Subscribe, then check a notification arrives byte-exactly."""
    value_handle, ccc_handle = await discover_notify_characteristic(central)
    await central.shell.run(f"gatt subscribe {ccc_handle:x} {value_handle:x}")
    await central.wait_log("Subscribed")
    # The CCC read on the same ATT bearer confirms notifications are enabled
    # before the server sends, avoiding timing sleeps.
    await central.shell.run(f"gatt read {ccc_handle:x}")
    await central.wait_log("Read complete: err 0x00 length 2")
    await central.wait_log("01 00")
    await peripheral.shell.run(f"gatt notify {value_handle:x} {payload.hex()}")
    await central.wait_log(
        rf"Notification: value_handle {value_handle}, length {len(payload)}"
    )
    for row in range(0, len(payload), 16):
        # shell_hexdump separates the two 8-octet halves with two spaces.
        octets = r"\s+".join(f"{value:02x}" for value in payload[row : row + 16])
        await central.wait_log(rf"(?i){row:08x}: {octets}")
