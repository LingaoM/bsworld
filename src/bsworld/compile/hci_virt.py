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
"""Validate the native Virtual Controller executable."""
from __future__ import annotations

import os
from pathlib import Path

from ..env import Env
from ..log import die


def _setup_hint(env: Env) -> str:
    return (
        "Build the Virtual Controller and export BSWORLD_BT_VIRT_CONTROLLER_BIN "
        "as the path to zephyr.exe. See components/bt_virt_controller/README.md."
    )


def controller_bin(env: Env) -> Path:
    """Return the Virtual Controller launcher path."""
    check_ready(env)
    return env.hci_virt_bin


def check_ready(env: Env) -> None:
    """Validate the launcher before pytest starts devices."""
    if env.hci_virt_bin is None or not env.hci_virt_bin.is_file() or not os.access(env.hci_virt_bin, os.X_OK):
        die(f"Virtual Controller executable unavailable: {env.hci_virt_bin}\n{_setup_hint(env)}", code=15)


__all__ = ["check_ready", "controller_bin"]
