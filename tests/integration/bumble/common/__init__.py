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
"""Shared Bumble test helpers."""

from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from pathlib import Path

import pytest

from bsworld.devices import Controller
from bsworld.topology import BluetoothTopology

try:
    from bumble import data_types
    from bumble.core import AdvertisingData
    from bumble.device import (
        AdvertisingEventProperties,
        AdvertisingParameters,
        AdvertisingType,
        Device,
        PeriodicAdvertisingParameters,
        PeriodicAdvertisingSync,
    )
    from bumble.hci import Address, OwnAddressType
    from bumble.transport import open_transport
except ModuleNotFoundError as exc:
    if exc.name != "bumble":
        raise
    pytest.skip(
        "Bumble is not installed; run: python -m pip install -e .",
        allow_module_level=True,
    )

ADVERTISER_ADDRESS = "F0:F1:F2:F3:F4:01"
OBSERVER_ADDRESS = "F0:F1:F2:F3:F4:02"
ADVERTISER_NAME = "BSWorld-Bumble"
PERIODIC_NAME = "BSWorld-PA"
TIMEOUT = 15.0

__all__ = [
    "ADVERTISER_ADDRESS",
    "ADVERTISER_NAME",
    "OBSERVER_ADDRESS",
    "PERIODIC_NAME",
    "TIMEOUT",
    "AdvertisingData",
    "AdvertisingEventProperties",
    "AdvertisingParameters",
    "AdvertisingType",
    "OwnAddressType",
    "PeriodicAdvertisingParameters",
    "PeriodicAdvertisingSync",
    "add_bumble_controller",
    "advertising_data",
    "open_bumble_device",
    "open_bumble_pair",
    "wait_for_advertisement",
]


def advertising_data(name: str) -> bytes:
    return bytes(
        AdvertisingData(
            [
                data_types.Flags(
                    AdvertisingData.LE_GENERAL_DISCOVERABLE_MODE_FLAG
                    | AdvertisingData.BR_EDR_NOT_SUPPORTED_FLAG
                ),
                data_types.CompleteLocalName(name),
            ]
        )
    )


async def open_bumble_device(
    stack: AsyncExitStack,
    name: str,
    address: str,
    hci_socket: str | Path,
) -> Device:
    transport = await stack.enter_async_context(
        await open_transport(f"unix:{hci_socket}")
    )
    device = Device.with_hci(name, Address(address), transport.source, transport.sink)
    await device.power_on()
    return device


async def wait_for_advertisement(
    device: Device,
    name: str,
    *,
    stop_scanning: bool = True,
) -> object:
    found = asyncio.get_running_loop().create_future()

    def on_advertisement(advertisement) -> None:  # noqa: ANN001
        if (
            not found.done()
            and advertisement.data.get(AdvertisingData.COMPLETE_LOCAL_NAME) == name
        ):
            found.set_result(advertisement)

    device.on("advertisement", on_advertisement)
    await device.start_scanning(active=False, filter_duplicates=False)
    try:
        return await asyncio.wait_for(found, timeout=TIMEOUT)
    finally:
        device.remove_listener("advertisement", on_advertisement)
        if stop_scanning:
            await device.stop_scanning()


def add_bumble_controller(
    topo: BluetoothTopology, role: str, address: str
) -> Controller:
    return topo.add_controller(
        public_address=address,
        log_subdir=Path("bumble") / role,
    )


async def open_bumble_pair(
    topo: BluetoothTopology, stack: AsyncExitStack
) -> tuple[Device, Device]:
    advertiser_ctl = add_bumble_controller(topo, "advertiser", ADVERTISER_ADDRESS)
    observer_ctl = add_bumble_controller(topo, "observer", OBSERVER_ADDRESS)
    topo.set_channel_attenuation(default_db=45.0)

    await topo.start()

    advertiser = await open_bumble_device(
        stack,
        "advertiser",
        ADVERTISER_ADDRESS,
        advertiser_ctl.hci_sock,
    )
    observer = await open_bumble_device(
        stack,
        "observer",
        OBSERVER_ADDRESS,
        observer_ctl.hci_sock,
    )
    return advertiser, observer
