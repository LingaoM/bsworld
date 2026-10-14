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
"""NuttX BTSak example binary profiles."""

from __future__ import annotations

from tests.integration.nuttx.common import NuttXProcessProfile


def _controller_address(group: int, index: int) -> str:
    if not (0 <= group <= 255 and 0 <= index <= 255):
        raise ValueError("controller address group/index must fit in one octet")
    return f"C0:FF:EE:00:{group:02X}:{index:02X}"


NUTTX_BTSAK_ADVERTISER = NuttXProcessProfile(
    name="nuttx_btsak_advertiser",
    binary_env="BSWORLD_NUTTX_BTSAK_BIN",
    controller_address=_controller_address(0, 1),
)

NUTTX_BTSAK_SCANNER = NuttXProcessProfile(
    name="nuttx_btsak_scanner",
    binary_env="BSWORLD_NUTTX_BTSAK_BIN",
    controller_address=_controller_address(1, 1),
)


def nuttx_btsak_advertiser(index: int) -> NuttXProcessProfile:
    return NuttXProcessProfile(
        name=f"nuttx_btsak_advertiser{index}",
        binary_env="BSWORLD_NUTTX_BTSAK_BIN",
        controller_address=_controller_address(0, index + 1),
    )


def nuttx_btsak_scanner(index: int) -> NuttXProcessProfile:
    return NuttXProcessProfile(
        name=f"nuttx_btsak_scanner{index}",
        binary_env="BSWORLD_NUTTX_BTSAK_BIN",
        controller_address=_controller_address(1, index + 1),
    )


__all__ = [
    "NUTTX_BTSAK_ADVERTISER",
    "NUTTX_BTSAK_SCANNER",
    "nuttx_btsak_advertiser",
    "nuttx_btsak_scanner",
]
