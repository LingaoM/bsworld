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

from tests.integration.applications import add_application, require_artifact

from bsworld.devices import AppSlot, Controller, ProcessInstance
from bsworld.env import env_path
from bsworld.topology import BluetoothTopology

_GUIDE = "tests/integration/zephyr/samples/README.md"


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
    """Skip before building a topology unless every executable is available."""
    for profile in profiles:
        require_artifact(profile.binary_env, guide=_GUIDE)


def sample_log_subdir(sample_name: str) -> Path:
    return Path("zephyr") / "samples" / sample_name


def _argv(binary: Path, slot: AppSlot) -> list[str | Path]:
    return [
        binary,
        f"-s={slot.sim_id}",
        f"-p={slot.phy_id}",
        f"-d={slot.dev_id}",
        "-mro=1000",
        f"--bt-dev={slot.hci_sock}",
    ]


def load_zephyr_profile(
    topo: BluetoothTopology,
    profile: ZephyrProcessProfile,
    *,
    log_subdir: Path | str | None = None,
    controller_type: type[Controller] | None = None,
) -> ProcessInstance:
    return add_application(
        topo,
        binary_env=profile.binary_env,
        guide=_GUIDE,
        argv=_argv,
        label=profile.name,
        controller_address=profile.controller_address,
        controller_type=controller_type,
        log_subdir=log_subdir,
    )


__all__ = [
    "ZephyrProcessProfile",
    "load_zephyr_profile",
    "require_binaries",
    "sample_log_subdir",
    "sample_profile",
]
