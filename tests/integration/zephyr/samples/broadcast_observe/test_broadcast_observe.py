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
"""Zephyr broadcaster and observer sample test."""

from __future__ import annotations

from dataclasses import replace

import pytest
from tests.integration.zephyr.samples.broadcast_observe.devices import ZEPHYR_BROADCASTER, ZEPHYR_OBSERVER
from tests.integration.zephyr.samples.common import load_zephyr_profile, require_binaries, sample_log_subdir

from bsworld.interference import StaticAttenuation

_TIMEOUT = 45.0
_BLE_ADVERTISING_CHANNELS_MHZ = (2402.0, 2426.0, 2480.0)
_INTERFERENCE_END_US = 5_000_000
_DEVICE_FOUND = r"Device found: .*RSSI"


async def test_zephyr_broadcaster_is_observed(topo):
    profiles = [ZEPHYR_BROADCASTER, ZEPHYR_OBSERVER]
    require_binaries(profiles)
    topo.set_channel_attenuation(default_db=45.0)
    broadcaster = load_zephyr_profile(
        topo,
        ZEPHYR_BROADCASTER,
        log_subdir=sample_log_subdir("broadcaster"),
    )
    observer = load_zephyr_profile(topo, ZEPHYR_OBSERVER, log_subdir=sample_log_subdir("observer"))

    await topo.start()

    await broadcaster.wait_log(r"Bluetooth initialized", timeout=_TIMEOUT)
    await observer.wait_log(r"Starting scanning\.\.\.", timeout=_TIMEOUT)
    await observer.wait_log(_DEVICE_FOUND, timeout=_TIMEOUT)


async def test_zephyr_targeted_interference_isolates_and_recovers(topo):
    jammed_observer_profile = replace(
        ZEPHYR_OBSERVER,
        name="zephyr_observer_jammed",
        controller_address="C0:FF:EE:41:00:03",
    )
    profiles = [ZEPHYR_BROADCASTER, ZEPHYR_OBSERVER, jammed_observer_profile]
    require_binaries(profiles)
    broadcaster = load_zephyr_profile(
        topo,
        ZEPHYR_BROADCASTER,
        log_subdir=sample_log_subdir("interference_broadcaster"),
    )
    protected_observer = load_zephyr_profile(
        topo,
        ZEPHYR_OBSERVER,
        log_subdir=sample_log_subdir("interference_observer_protected"),
    )
    jammed_observer = load_zephyr_profile(
        topo,
        jammed_observer_profile,
        log_subdir=sample_log_subdir("interference_observer_jammed"),
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
            StaticAttenuation(tx=broadcaster, rx=protected_observer, attenuation_db=45.0),
            StaticAttenuation(tx=broadcaster, rx=jammed_observer, attenuation_db=45.0),
            *(
                StaticAttenuation(tx=jammer, rx=protected_observer, attenuation_db=100.0)
                for jammer in jammers
            ),
            *(
                StaticAttenuation(tx=jammer, rx=jammed_observer, attenuation_db=0.0)
                for jammer in jammers
            ),
        ],
    )

    await topo.start()

    await protected_observer.wait_log(_DEVICE_FOUND, timeout=_TIMEOUT)
    with pytest.raises(TimeoutError):
        await jammed_observer.wait_log(_DEVICE_FOUND, timeout=2.0)
    await jammed_observer.wait_log(_DEVICE_FOUND, timeout=_TIMEOUT)
