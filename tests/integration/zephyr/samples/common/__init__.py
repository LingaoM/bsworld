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

from bsworld.devices import Controller, ProcessInstance
from bsworld.env import env_path
from bsworld.topology import BluetoothTopology


@dataclass(frozen=True)
class ZephyrProcessProfile:
    name: str
    binary_env: str
    controller_address: str

    @property
    def path(self) -> Path | None:
        return env_path(self.binary_env)


def sample_profile(sample_name: str, address: str) -> ZephyrProcessProfile:
    return ZephyrProcessProfile(
        name=f"zephyr_{sample_name}",
        binary_env=f"BSWORLD_ZEPHYR_{sample_name.upper()}_BIN",
        controller_address=address,
    )


def require_binaries(profiles: list[ZephyrProcessProfile]) -> None:
    for profile in profiles:
        path = profile.path
        if path is None or not path.is_file() or not path.stat().st_mode & 0o111:
            pytest.skip(f"Set {profile.binary_env} to the compiled Zephyr executable; "
                        "see tests/integration/zephyr/samples/README.md.")


def sample_log_subdir(sample_name: str) -> Path:
    return Path("zephyr") / "samples" / sample_name


def load_zephyr_profile(
    topo: BluetoothTopology,
    profile: ZephyrProcessProfile,
    *,
    log_subdir: Path | str | None = None,
    controller_type: type[Controller] | None = None,
) -> ProcessInstance:
    require_binaries([profile])
    options = {"controller_type": controller_type} if controller_type is not None else {}
    controller = topo.add_controller(public_address=profile.controller_address, **options)
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
