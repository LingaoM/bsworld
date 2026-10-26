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
"""Register an externally built Application with a topology.

Every suite resolves its executable from an environment variable, skips when
that artifact is absent, allocates a Virtual Controller, and registers a
process whose argv is built from the assigned device slot. Only the argv and
the setup instructions differ, so the shared steps live here.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from bsworld.devices import AppSlot, Controller, ProcessInstance
from bsworld.env import env_path
from bsworld.topology import BluetoothTopology

ArgvFactory = Callable[[AppSlot], list[str | Path]]


def require_artifact(binary_env: str, *, guide: str, executable: bool = True) -> Path:
    """Resolve an artifact selected by an environment variable, or skip.

    The variable is read on every call so a test can change the selected
    artifact without reimporting the profiles that name it.
    """
    path = env_path(binary_env)
    if (
        path is None
        or not path.is_file()
        or (executable and not path.stat().st_mode & 0o111)
    ):
        kind = "compiled executable" if executable else "built artifact"
        pytest.skip(f"Set {binary_env} to the {kind}; see {guide}.")
    return path


def add_application(
    topo: BluetoothTopology,
    *,
    argv: Callable[[Path, AppSlot], list[str | Path]],
    label: str,
    binary: Path | None = None,
    binary_env: str | None = None,
    guide: str | None = None,
    controller_address: str | None = None,
    controller_type: type[Controller] | None = None,
    controller_log_subdir: Path | str | None = None,
    log_subdir: Path | str | None = None,
    shell: bool = False,
) -> ProcessInstance:
    """Attach one native Application and its Virtual Controller to a topology.

    Name the executable with binary_env to skip when the artifact is absent, or
    pass an already resolved binary when the suite reports a missing build
    itself.

    argv receives the executable and the device slot assigned once the topology
    is complete, so it never has to read an unassigned identity. Omitting
    controller_type uses the topology's default, which lets a suite run the same
    scenario against either Controller implementation.
    """
    if (binary is None) == (binary_env is None):
        raise TypeError("pass exactly one of binary or binary_env")
    if binary is None:
        if guide is None:
            raise TypeError("binary_env requires guide")
        binary = require_artifact(binary_env, guide=guide)
    executable = binary.absolute()
    controller = topo.add_controller(
        controller_type=controller_type,
        public_address=controller_address,
        log_subdir=controller_log_subdir,
    )
    return topo.add_process(
        ProcessInstance(
            command=lambda slot: argv(executable, slot),
            controller=controller,
            label=label,
            shell=shell,
            log_subdir=log_subdir,
        )
    )


__all__ = ["ArgvFactory", "add_application", "require_artifact"]
