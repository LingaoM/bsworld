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
"""Zephyr periodic_adv and periodic_sync sample test."""

from __future__ import annotations

from tests.integration.zephyr.samples.common import load_zephyr_profile, require_binaries, sample_log_subdir
from tests.integration.zephyr.samples.periodic_advertising.devices import ZEPHYR_PERIODIC_ADV, ZEPHYR_PERIODIC_SYNC

_TIMEOUT = 90.0


async def test_zephyr_periodic_sync_receives_periodic_advertising(topo):
    profiles = [ZEPHYR_PERIODIC_ADV, ZEPHYR_PERIODIC_SYNC]
    require_binaries(profiles)
    topo.set_channel_attenuation(default_db=45.0)
    advertiser = load_zephyr_profile(
        topo,
        ZEPHYR_PERIODIC_ADV,
        log_subdir=sample_log_subdir("periodic_adv"),
    )
    sync = load_zephyr_profile(topo, ZEPHYR_PERIODIC_SYNC, log_subdir=sample_log_subdir("periodic_sync"))

    await topo.start()

    await advertiser.wait_log(r"Start Extended Advertising\.\.\.done\.", timeout=_TIMEOUT)
    await sync.wait_log(r"Found periodic advertising\.", timeout=_TIMEOUT)
    await sync.wait_log(r"Periodic sync established\.", timeout=_TIMEOUT)
    await sync.wait_log(r"PER_ADV_SYNC\[\d+\]: .*data length", timeout=_TIMEOUT)
