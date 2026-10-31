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
"""NuttX NimBLE example binary profiles."""

from __future__ import annotations

from tests.integration.nuttx.common import NuttXProcessProfile

DEFAULT_DEVICE_NAME = "NuttX NimBLE PRPH"


NUTTX_NIMBLE_PERIPHERAL = NuttXProcessProfile(
    name="nuttx_nimble_peripheral",
    binary_env="BSWORLD_NUTTX_NIMBLE_BIN",
)

NUTTX_NIMBLE_CENTRAL = NuttXProcessProfile(
    name="nuttx_nimble_central",
    binary_env="BSWORLD_NUTTX_NIMBLE_BIN",
)


__all__ = [
    "DEFAULT_DEVICE_NAME",
    "NUTTX_NIMBLE_CENTRAL",
    "NUTTX_NIMBLE_PERIPHERAL",
]
