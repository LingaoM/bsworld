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
"""Zephyr central_hr and peripheral_hr sample test."""

from __future__ import annotations

from tests.integration.zephyr.samples.common import load_zephyr_profile, require_binaries, sample_log_subdir
from tests.integration.zephyr.samples.heart_rate.devices import ZEPHYR_CENTRAL_HR, ZEPHYR_PERIPHERAL_HR

_TIMEOUT = 60.0


async def test_zephyr_central_hr_receives_heart_rate_notifications(topo):
    profiles = [ZEPHYR_PERIPHERAL_HR, ZEPHYR_CENTRAL_HR]
    require_binaries(profiles)
    topo.set_channel_attenuation(default_db=45.0)
    peripheral = load_zephyr_profile(
        topo,
        ZEPHYR_PERIPHERAL_HR,
        log_subdir=sample_log_subdir("peripheral_hr"),
    )
    central = load_zephyr_profile(topo, ZEPHYR_CENTRAL_HR, log_subdir=sample_log_subdir("central_hr"))

    await topo.start()

    await peripheral.wait_log(r"Advertising successfully started", timeout=_TIMEOUT)
    await central.wait_log(r"Scanning successfully started", timeout=_TIMEOUT)
    await central.wait_log(r"Connected: .*", timeout=_TIMEOUT)
    await peripheral.wait_log(r"Connected", timeout=_TIMEOUT)
    await central.wait_log(r"\[SUBSCRIBED\]", timeout=_TIMEOUT)
    await central.wait_log(r"\[NOTIFICATION\] data .* length", timeout=_TIMEOUT)
