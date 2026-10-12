# Copyright 2026 Xiaomi Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""TrouBLE's Linux example running inside a synchronized QEMU guest."""

from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from pathlib import Path

from tests.integration.bumble.common import (
    AdvertisingData,
    add_bumble_controller,
    open_bumble_device,
)
from tests.integration.qemu.common import load_qemu_guest, login_qemu_guest

from bsworld.topology import BluetoothTopology

_CONTROLLER_ADDRESS = "AA:BB:CC:DD:EE:FD"
_TROUBLE_ADDRESS = "FF:E4:05:1A:8F:FF"
_TROUBLE_NAME = "Trouble Example"
_BUMBLE_CENTRAL_ADDRESS = "F0:F1:F2:F3:F4:13"
_TIMEOUT = 20.0


async def test_qemu_trouble_linux_advertises_and_serves_battery_level(
    topo: BluetoothTopology,
) -> None:
    guest = load_qemu_guest(
        topo,
        controller_address=_CONTROLLER_ADDRESS,
        label="qemu_trouble",
        log_subdir=Path("qemu") / "trouble",
    )
    central_ctl = add_bumble_controller(topo, "qemu_trouble_central", _BUMBLE_CENTRAL_ADDRESS)
    topo.set_channel_attenuation(default_db=45.0)
    await topo.start()

    await login_qemu_guest(guest)
    async with AsyncExitStack() as stack:
        central = await open_bumble_device(
            stack,
            "qemu_trouble_central",
            _BUMBLE_CENTRAL_ADDRESS,
            central_ctl.hci_sock,
        )
        found = asyncio.get_running_loop().create_future()

        def on_advertisement(advertisement) -> None:  # noqa: ANN001
            name = advertisement.data.get(AdvertisingData.COMPLETE_LOCAL_NAME)
            if not found.done() and name == _TROUBLE_NAME:
                found.set_result(advertisement)

        central.on("advertisement", on_advertisement)
        await central.start_scanning(active=False, filter_duplicates=False)
        connection = None
        try:
            await guest.shell.run("killall bluetoothd 2>/dev/null || true")
            await guest.shell.run("btattach -B /dev/ttyS0 -P h4 -S 1000000 -N &")
            await guest.wait_log(r"Device index 0 attached", timeout=_TIMEOUT)
            await guest.shell.run("hciconfig hci0 down")
            await guest.shell.run("RUST_LOG=info trouble-ble-bas-peripheral 0 &")
            await guest.wait_log(r"Starting advertising and GATT service", timeout=_TIMEOUT)

            advertisement = await asyncio.wait_for(found, timeout=_TIMEOUT)
            assert advertisement.address.to_string(with_type_qualifier=False) == _TROUBLE_ADDRESS

            await central.stop_scanning()
            connection = await central.connect(advertisement.address, timeout=_TIMEOUT)
            assert connection.handle is not None

            services = await connection.gatt_client.discover_service("180F")
            assert len(services) == 1
            characteristics = await connection.gatt_client.discover_characteristics(["2A19"], services[0])
            assert len(characteristics) == 1
            battery_level = await characteristics[0].read_value()
            assert len(battery_level) == 1
            assert 0 <= battery_level[0] <= 100
        finally:
            central.remove_listener("advertisement", on_advertisement)
            if central.is_scanning:
                await central.stop_scanning()
            if connection is not None:
                await connection.disconnect()
