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
"""Path / env resolution for bsworld.

A single Env instance is created per pytest run and threaded through every
backend, build, and runtime module.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def repo_root() -> Path:
    return _REPO_ROOT


def env_path(name: str) -> Path | None:
    """Resolve a configured artifact without assuming a build location."""
    value = os.environ.get(name)
    return Path(value).expanduser().resolve() if value else None


def _now_tag() -> str:
    return "run-" + datetime.now().strftime("%Y%m%d_%H%M%S")


def _run_uid() -> str:
    return uuid.uuid4().hex[:8]


@dataclass(frozen=True)
class Env:
    out_tag: str
    run_uid: str
    out_dir: Path
    log_dir: Path

    # BabbleSim source submodules and default component workspace
    babblesim_root: Path

    # Native artifacts are selected explicitly before pytest starts.
    hci_virt_bin: Path | None

    # shared build outputs prepared before pytest
    bsim_dir: Path | None
    bsim_bin_dir: Path | None

    bs_state_dir: Path

    bsim_ellisys: bool = True
    bsim_ellisys_script: Path | None = None

    @classmethod
    def detect(
        cls,
        *,
        out_tag: str | None = None,
        now_tag: str | None = None,
        run_uid: str | None = None,
        bsim_ellisys: bool = True,
    ) -> "Env":
        base_dir = Path(out_tag or os.environ.get("OUT_DIR") or "/tmp")
        resolved_tag = now_tag or _now_tag()
        uid = run_uid or os.environ.get("RUN_UID") or _run_uid()
        out_dir = base_dir / resolved_tag / uid
        log_dir = out_dir / "log"

        bsim_dir = env_path("BSWORLD_BSIM_DIR")

        import pwd
        user = pwd.getpwuid(os.getuid()).pw_name

        return cls(
            out_tag=resolved_tag,
            run_uid=uid,
            out_dir=out_dir,
            log_dir=log_dir,
            babblesim_root=_REPO_ROOT / "components" / "babblesim",
            hci_virt_bin=env_path("BSWORLD_BT_VIRT_CONTROLLER_BIN"),
            bsim_dir=bsim_dir,
            bsim_bin_dir=bsim_dir / "bin" if bsim_dir else None,
            bs_state_dir=Path("/tmp") / f"bs_{user}",
            bsim_ellisys=bsim_ellisys,
            bsim_ellisys_script=env_path("BSWORLD_BSIM_ELLISYS_SCRIPT"),
        )

    def sim_dir(self, sim_id: str) -> Path:
        return self.bs_state_dir / sim_id

    @property
    def babblesim_components_dir(self) -> Path:
        return self.babblesim_root / "components"
