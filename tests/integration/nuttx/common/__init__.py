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
"""NuttX process helpers for repository integration tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from bsworld.devices import ProcessInstance
from bsworld.env import env_path
from bsworld.topology import BluetoothTopology


@dataclass(frozen=True)
class NuttXProcessProfile:
    name: str
    binary_env: str
    shell: bool = True
    controller_address: str | None = None

    @property
    def path(self) -> Path | None:
        return env_path(self.binary_env)


def require_binaries(profiles: list[NuttXProcessProfile]) -> None:
    for profile in profiles:
        path = profile.path
        if path is None or not path.is_file() or not path.stat().st_mode & 0o111:
            pytest.skip(f"Set {profile.binary_env} to the compiled NuttX executable; "
                        "see tests/integration/nuttx/README.md.")


def load_nuttx_profile(
    topo: BluetoothTopology,
    profile: NuttXProcessProfile,
    *,
    log_subdir: Path | str | None = None,
) -> ProcessInstance:
    require_binaries([profile])
    controller = topo.add_controller(public_address=profile.controller_address)
    binary = profile.path.absolute()

    def command() -> list[str | Path]:
        if controller.application_dev_id is None:
            raise RuntimeError("NuttX process requires a BabbleSim device id")
        return [
            binary,
            f"--sim-bsim-sid={controller.sim_id}",
            f"--sim-bsim-pid={controller.phy_id}",
            f"--sim-bsim-dev={controller.application_dev_id}",
            f"--bt-dev={controller.hci_sock}",
        ]

    return topo.add_process(
        ProcessInstance(
            command=command,
            controller=controller,
            label=profile.name,
            shell=profile.shell,
            log_subdir=log_subdir,
        )
    )


__all__ = [
    "NuttXProcessProfile",
    "load_nuttx_profile",
    "require_binaries",
]
