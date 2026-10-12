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
"""Zephyr mesh and mesh_provisioner sample profiles."""

from __future__ import annotations

from pathlib import Path

from tests.integration.zephyr.samples.common import sample_profile

GROUP_DIR = Path(__file__).resolve().parent

ZEPHYR_MESH = sample_profile(GROUP_DIR, "mesh", "C0:FF:EE:41:03:01")
ZEPHYR_MESH_PROVISIONER = sample_profile(GROUP_DIR, "mesh_provisioner", "C0:FF:EE:41:03:02")

__all__ = ["ZEPHYR_MESH", "ZEPHYR_MESH_PROVISIONER"]
