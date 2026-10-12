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

from pathlib import Path

from tests.integration.nuttx.common import NuttXProcessProfile

_PREBUILT_DIR = Path(__file__).resolve().parent / "prebuilt"
DEFAULT_DEVICE_NAME = "NuttX NimBLE PRPH"
_NUTTX_BINARY = _PREBUILT_DIR / "nuttx" / "exodus" / "bin" / "nuttx"


def _controller_address(group: int, index: int) -> str:
    if not (0 <= group <= 255 and 0 <= index <= 255):
        raise ValueError("controller address group/index must fit in one octet")
    return f"C0:FF:EE:20:{group:02X}:{index:02X}"


NUTTX_NIMBLE_PERIPHERAL = NuttXProcessProfile(
    name="nuttx_nimble_peripheral",
    path=_NUTTX_BINARY,
    controller_address=_controller_address(0, 1),
)

NUTTX_NIMBLE_CENTRAL = NuttXProcessProfile(
    name="nuttx_nimble_central",
    path=_NUTTX_BINARY,
    controller_address=_controller_address(1, 1),
)


__all__ = [
    "DEFAULT_DEVICE_NAME",
    "NUTTX_NIMBLE_CENTRAL",
    "NUTTX_NIMBLE_PERIPHERAL",
]
