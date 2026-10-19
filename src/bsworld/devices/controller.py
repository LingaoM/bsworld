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
"""Virtual Controller endpoint allocated for one Bluetooth Host."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


def normalize_controller_address(address: str) -> str:
    parts = address.split(":")
    if len(parts) != 6:
        raise ValueError("controller address must use AA:BB:CC:DD:EE:FF format")

    octets: list[str] = []
    for part in parts:
        if len(part) != 2:
            raise ValueError("controller address must use AA:BB:CC:DD:EE:FF format")
        try:
            value = int(part, 16)
        except ValueError as exc:
            raise ValueError("controller address must use AA:BB:CC:DD:EE:FF format") from exc
        octets.append(f"{value:02X}")

    if all(octet == "00" for octet in octets):
        raise ValueError("controller address must not be all zero")

    return ":".join(octets)


@dataclass
class Controller:
    controller_dev_id: int
    sim_id: str
    phy_id: str
    socket_dir: Path
    application_dev_id: int | None
    public_address: str | None = None
    hci_snoop_file: Path | None = None

    @property
    def hci_sock(self) -> Path:
        return self.socket_dir / f"hci{self.controller_dev_id}.sock"

    def __repr__(self) -> str:
        return f"<Controller dev{self.controller_dev_id}>"


__all__ = ["Controller", "normalize_controller_address"]
