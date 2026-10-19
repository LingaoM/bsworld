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
"""Validate the selected BabbleSim runtime artifacts."""
from __future__ import annotations

import os

from ..env import Env
from ..log import die

_OUTPUTS = (
    "bin/bs_2G4_phy_v1",
    "bin/bs_device_2G4_burst_interf",
    "bin/bs_device_2G4_WLAN_actmod",
    "bin/bs_device_2G4_playback",
    "bin/bs_device_2G4_playbackv2",
    "lib/lib_2G4Channel_NtNcable.so",
    "lib/lib_2G4Channel_multiatt.so",
    "lib/lib_2G4Modem_BLE_simple.so",
    "lib/lib_2G4Modem_Magic.so",
    "lib/libPhyComv1.so",
    "lib/libPhyComv1.32.so",
    "lib/libUtilv1.so",
    "lib/libUtilv1.32.so",
)


def _manual_setup_hint(env: Env) -> str:
    return (
        "Follow the repo-based BabbleSim setup in README.md#build-and-test, "
        "then set BSIM_OUT_PATH to the build output directory "
        f"containing bin/ and lib/ (currently {env.bsim_dir}).\n"
    )


def check_ready(env: Env) -> None:
    """Validate BabbleSim runtime outputs before pytest."""
    if env.bsim_dir is None:
        die("Set BSIM_OUT_PATH to the BabbleSim output directory containing bin/ and lib/. "
            "See README.md.", code=15)
    missing_outputs = [
        str(env.bsim_dir / rel)
        for rel in _OUTPUTS
        if not (env.bsim_dir / rel).is_file()
        or (rel.startswith("bin/") and not os.access(env.bsim_dir / rel, os.X_OK))
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
