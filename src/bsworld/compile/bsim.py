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
"""Validate manually built BabbleSim artifacts."""
from __future__ import annotations

from ..env import Env
from ..log import die

_BASE_DIR = "base"
_REQUIRED_SUBMODULES = (
    (_BASE_DIR, "common/pre.make.inc"),
    ("ext_2G4_channel_NtNcable", "Depends"),
    ("ext_2G4_channel_multiatt", "Depends"),
    ("ext_2G4_device_WLAN_actmod", "Depends"),
    ("ext_2G4_device_burst_interferer", "Depends"),
    ("ext_2G4_device_playback", "Depends"),
    ("ext_2G4_device_playbackv2", "Depends"),
    ("ext_2G4_libPhyComv1", "Depends"),
    ("ext_2G4_modem_BLE_simple", "Depends"),
    ("ext_2G4_modem_magic", "Depends"),
    ("ext_2G4_phy_v1", "Depends"),
)
_REQUIRED_COMPONENTS = (
    "common",
    "libPhyComv1",
    "libRandv2",
    "libUtilv1",
    "ext_2G4_channel_NtNcable",
    "ext_2G4_channel_multiatt",
    "ext_2G4_device_WLAN_actmod",
    "ext_2G4_device_burst_interferer",
    "ext_2G4_device_playback",
    "ext_2G4_device_playbackv2",
    "ext_2G4_libPhyComv1",
    "ext_2G4_modem_BLE_simple",
    "ext_2G4_modem_magic",
    "ext_2G4_phy_v1",
)
_OUTPUTS = (
    "bin/bs_2G4_phy_v1",
    "bin/bs_device_2G4_burst_interf",
    "bin/bs_device_2G4_WLAN_actmod",
    "bin/bs_device_2G4_playback",
    "bin/bs_device_2G4_playbackv2",
)


def _ensure_submodules_ready(env: Env) -> None:
    missing = [
        str(env.babblesim_root / rel / marker)
        for rel, marker in _REQUIRED_SUBMODULES
        if not (env.babblesim_root / rel / marker).is_file()
    ]
    if missing:
        formatted = "\n    ".join(missing)
        die(
            "BabbleSim submodules are not initialized. Run:\n"
            "    git submodule update --init --recursive components/babblesim\n"
            f"Missing:\n    {formatted}",
            code=15,
        )


def _ensure_default_workspace_ready(env: Env) -> None:
    missing = []
    if not (env.babblesim_root / "Makefile").is_file():
        missing.append(str(env.babblesim_root / "Makefile"))
    for name in _REQUIRED_COMPONENTS:
        marker = "pre.make.inc" if name == "common" else "Depends"
        missing_path = env.babblesim_components_dir / name / marker
        if not missing_path.is_file():
            missing.append(str(missing_path))
    if missing:
        formatted = "\n    ".join(missing)
        die(
            "BabbleSim default workspace is incomplete. Expected "
            "`components/babblesim/Makefile` and `components/babblesim/components/`.\n"
            f"Missing:\n    {formatted}",
            code=15,
        )


def _manual_setup_hint(env: Env) -> str:
    return (
        "Run the manual BabbleSim setup steps before pytest:\n"
        "    git submodule update --init --recursive components/babblesim\n"
        f"    export BSIM_OUT_PATH={env.bsim_dir}\n"
        f"    export BSIM_COMPONENTS_PATH={env.babblesim_components_dir}\n"
        "    export BSIM_BASE_PATH=$BSIM_COMPONENTS_PATH\n"
        "    export BSIM_BUILD_FAIL_ASAP=1\n"
        "    make -C components/babblesim everything\n"
    )


def check_ready(env: Env) -> None:
    """Validate that BabbleSim was manually built before pytest."""
    _ensure_submodules_ready(env)
    _ensure_default_workspace_ready(env)
    missing_outputs = [
        str(env.bsim_dir / rel)
        for rel in _OUTPUTS
        if not (env.bsim_dir / rel).is_file()
    ]
    if missing_outputs:
        die(
            "BabbleSim build outputs are missing.\n"
            "Missing:\n    "
            + "\n    ".join(missing_outputs)
            + "\n"
            + _manual_setup_hint(env),
            code=15,
        )
