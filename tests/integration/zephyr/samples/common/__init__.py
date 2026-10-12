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
"""Shared helpers for Zephyr Bluetooth sample tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from bsworld.devices import ProcessInstance
from bsworld.topology import BluetoothTopology


@dataclass(frozen=True)
class ZephyrProcessProfile:
    name: str
    path: Path
    controller_address: str


def sample_profile(group_dir: Path, sample_name: str, address: str) -> ZephyrProcessProfile:
    return ZephyrProcessProfile(
        name=f"zephyr_{sample_name}",
        path=group_dir / "prebuilt" / sample_name / "exodus" / "bin" / "zephyr.exe",
        controller_address=address,
    )


def require_binaries(profiles: list[ZephyrProcessProfile]) -> None:
    missing = [str(profile.path) for profile in profiles if not profile.path.is_file()]
    if missing:
        pytest.skip(
            "Zephyr sample binaries are not built; see "
            "tests/integration/zephyr/samples/README.md. Missing: " + ", ".join(missing)
        )


def sample_log_subdir(sample_name: str) -> Path:
    return Path("zephyr") / "samples" / sample_name


def load_zephyr_profile(
    topo: BluetoothTopology,
    profile: ZephyrProcessProfile,
    *,
    log_subdir: Path | str | None = None,
) -> ProcessInstance:
    controller = topo.add_controller(public_address=profile.controller_address)
    binary = profile.path.absolute()

    def command() -> list[str | Path]:
        if controller.application_dev_id is None:
            raise RuntimeError("Zephyr process requires a BabbleSim device id")
        return [
            binary,
            f"-s={controller.sim_id}",
            f"-p={controller.phy_id}",
            f"-d={controller.application_dev_id}",
            "-mro=1000",
            f"--bt-dev={controller.hci_sock}",
        ]

    return topo.add_process(
        ProcessInstance(
            command=command,
            controller=controller,
            label=profile.name,
            log_subdir=log_subdir,
        )
    )


__all__ = [
    "ZephyrProcessProfile",
    "load_zephyr_profile",
    "require_binaries",
    "sample_log_subdir",
    "sample_profile",
]
