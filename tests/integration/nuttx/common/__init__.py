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

from tests.integration.applications import create_application, require_artifact

from bsworld.devices import AppSlot, ProcessInstance
from bsworld.env import env_path
from bsworld.topology import BluetoothTopology

_GUIDE = "tests/integration/nuttx/README.md"


@dataclass(frozen=True)
class NuttXProcessProfile:
    """Program identity and console behavior, independent of the test topology."""

    name: str
    binary_env: str
    shell: bool = True

    @property
    def path(self) -> Path | None:
        return env_path(self.binary_env)


def require_binaries(profiles: list[NuttXProcessProfile]) -> None:
    """Skip before building a topology unless every executable is available."""
    for profile in profiles:
        require_artifact(profile.binary_env, guide=_GUIDE)


def _argv(binary: Path, slot: AppSlot) -> list[str | Path]:
    return [
        binary,
        f"--sim-bsim-sid={slot.sim_id}",
        f"--sim-bsim-pid={slot.phy_id}",
        f"--sim-bsim-dev={slot.dev_id}",
        f"--bt-dev={slot.hci_sock}",
    ]


def create_nuttx_process(
    topo: BluetoothTopology,
    profile: NuttXProcessProfile,
    *,
    log_subdir: Path | str | None = None,
) -> ProcessInstance:
    return create_application(
        topo,
        binary_env=profile.binary_env,
        guide=_GUIDE,
        argv=_argv,
        label=profile.name,
        log_subdir=log_subdir,
        shell=profile.shell,
    )


__all__ = [
    "NuttXProcessProfile",
    "create_nuttx_process",
    "require_binaries",
]
