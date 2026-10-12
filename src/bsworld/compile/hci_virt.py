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
"""Validate the expanded virtual HCI controller runtime."""
from __future__ import annotations

from pathlib import Path

from ..env import Env
from ..log import die


def _setup_hint(env: Env) -> str:
    return (
        "Install the matching prebuilt release or build the Virtual Controller before pytest:\n"
        f"    {env.hci_virt_bin}"
    )


def controller_bin(env: Env) -> Path:
    """Return the Virtual Controller launcher path."""
    return env.hci_virt_bin


def check_ready(env: Env) -> None:
    """Validate the launcher before pytest starts devices."""
    if not env.hci_virt_bin.is_file():
        die(f"hci_virt launcher not found: {env.hci_virt_bin}\n{_setup_hint(env)}", code=15)


__all__ = ["check_ready", "controller_bin"]
