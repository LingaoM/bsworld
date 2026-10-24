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
#
"""Exercise both Controller implementations together through real PHY traffic."""

from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from dataclasses import replace

import pytest
from tests.integration.bumble.common import (
    ADVERTISER_ADDRESS,
    OBSERVER_ADDRESS,
    TIMEOUT,
    AdvertisingData,
    OwnAddressType,
    advertising_data,
    open_bumble_device,
    wait_for_advertisement,
)

from bsworld.devices import BSController, ZephyrController


@pytest.mark.parametrize(
    ("peripheral_type", "central_type"),
    [
        (ZephyrController, ZephyrController),
        (BSController, ZephyrController),
        (ZephyrController, BSController),
        (BSController, BSController),
    ],
    ids=["zephyr-zephyr", "python-zephyr", "zephyr-python", "python-python"],
)
async def test_controller_pair_scans_connects_and_disconnects(topo, peripheral_type, central_type):
    if peripheral_type is BSController and central_type is BSController:
        # A pure Python topology must not depend on a Zephyr executable.
        topo.env = replace(topo.env, hci_virt_bin=None)
        topo.bsim.env = topo.env
    peripheral_ctl = topo.add_controller(controller_type=peripheral_type, public_address=ADVERTISER_ADDRESS)
    central_ctl = topo.add_controller(controller_type=central_type, public_address=OBSERVER_ADDRESS)
    topo.set_channel_attenuation(default_db=45.0)
    await topo.start()
    async with AsyncExitStack() as stack:
        peripheral = await open_bumble_device(stack, "peripheral", ADVERTISER_ADDRESS, peripheral_ctl.hci_sock)
        central = await open_bumble_device(stack, "central", OBSERVER_ADDRESS, central_ctl.hci_sock)
        connected = asyncio.Event()
        disconnected = asyncio.Event()

        def on_connection(connection):
            connected.set()
            connection.on("disconnection", lambda _: disconnected.set())

        peripheral.on("connection", on_connection)
        name = "BSWorld-Controllers"
        await peripheral.start_advertising(
            own_address_type=OwnAddressType.PUBLIC,
            advertising_data=advertising_data(name),
            advertising_interval_min=20.0,
            advertising_interval_max=20.0,
        )
        try:
            report = await wait_for_advertisement(central, name)
            assert report.address == peripheral.public_address
            connection = await central.connect(peripheral.public_address, timeout=TIMEOUT)
            await asyncio.wait_for(connected.wait(), TIMEOUT)
            await connection.disconnect()
            await asyncio.wait_for(disconnected.wait(), TIMEOUT)
        finally:
            await peripheral.stop_advertising()


async def test_native_zephyr_host_uses_python_controller(topo):
    from tests.integration.zephyr.samples.broadcast_observe.devices import ZEPHYR_BROADCASTER
    from tests.integration.zephyr.samples.common import load_zephyr_profile

    broadcaster = load_zephyr_profile(topo, ZEPHYR_BROADCASTER, controller_type=BSController)
    observer_ctl = topo.add_controller(public_address=OBSERVER_ADDRESS)
    topo.set_channel_attenuation(default_db=45.0)
    await topo.start()
    assert topo.bsim.plan_devices().application_slot(broadcaster.controller).dev_id == 2
    async with AsyncExitStack() as stack:
        observer = await open_bumble_device(stack, "observer", OBSERVER_ADDRESS, observer_ctl.hci_sock)
        found = asyncio.get_running_loop().create_future()

        def on_advertisement(report):
            manufacturer_data = report.data.get(AdvertisingData.MANUFACTURER_SPECIFIC_DATA)
            if manufacturer_data is not None and manufacturer_data[0] == 0xFFFF and not found.done():
                found.set_result(report)

        observer.on("advertisement", on_advertisement)
        await broadcaster.wait_log("Bluetooth initialized", timeout=TIMEOUT)
        await observer.start_scanning(active=False)
        try:
            report = await asyncio.wait_for(found, TIMEOUT)
            company, payload = report.data.get(AdvertisingData.MANUFACTURER_SPECIFIC_DATA)
            assert company == 0xFFFF
            assert len(payload) == 1
        finally:
            await observer.stop_scanning()
