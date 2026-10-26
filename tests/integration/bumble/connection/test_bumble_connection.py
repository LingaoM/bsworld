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
"""Bumble central and peripheral connection test."""

from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack

from tests.integration.bumble.common import (
    ADVERTISER_NAME,
    TIMEOUT,
    AdvertisingType,
    OwnAddressType,
    advertising_data,
    open_bumble_pair,
)


async def test_bumble_central_connects_bumble_peripheral(topo):
    peripheral_connected = asyncio.Event()

    async with AsyncExitStack() as stack:
        peripheral, central = await open_bumble_pair(topo, stack)
        peripheral.on("connection", lambda _: peripheral_connected.set())

        await peripheral.start_advertising(
            advertising_type=AdvertisingType.UNDIRECTED_CONNECTABLE_SCANNABLE,
            own_address_type=OwnAddressType.PUBLIC,
            advertising_data=advertising_data(ADVERTISER_NAME),
            advertising_interval_min=20.0,
            advertising_interval_max=20.0,
        )
        connection = None
        try:
            connection = await central.connect(
                peripheral.public_address, timeout=TIMEOUT
            )
            await asyncio.wait_for(peripheral_connected.wait(), timeout=TIMEOUT)
            assert connection.handle is not None
        finally:
            if connection is not None:
                await connection.disconnect()
            await peripheral.stop_advertising()
