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
"""Zephyr central_hr and peripheral_hr sample profiles."""

from __future__ import annotations

from tests.integration.zephyr.samples.common import sample_profile

ZEPHYR_PERIPHERAL_HR = sample_profile("peripheral_hr", "C0:FF:EE:41:01:01")
ZEPHYR_CENTRAL_HR = sample_profile("central_hr", "C0:FF:EE:41:01:02")

__all__ = ["ZEPHYR_CENTRAL_HR", "ZEPHYR_PERIPHERAL_HR"]
