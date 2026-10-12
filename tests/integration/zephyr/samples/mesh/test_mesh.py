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
"""Zephyr mesh and mesh_provisioner sample test."""

from __future__ import annotations

from tests.integration.zephyr.samples.common import load_zephyr_profile, require_binaries, sample_log_subdir
from tests.integration.zephyr.samples.mesh.devices import ZEPHYR_MESH, ZEPHYR_MESH_PROVISIONER

_TIMEOUT = 180.0


async def test_zephyr_mesh_provisioner_adds_mesh_node(topo):
    profiles = [ZEPHYR_MESH_PROVISIONER, ZEPHYR_MESH]
    require_binaries(profiles)
    topo.set_channel_attenuation(default_db=45.0)
    provisioner = load_zephyr_profile(
        topo,
        ZEPHYR_MESH_PROVISIONER,
        log_subdir=sample_log_subdir("mesh_provisioner"),
    )
    mesh = load_zephyr_profile(topo, ZEPHYR_MESH, log_subdir=sample_log_subdir("mesh"))

    await topo.start()

    await provisioner.wait_log(r"Provisioning completed", timeout=_TIMEOUT)
    await mesh.wait_log(r"Mesh initialized", timeout=_TIMEOUT)
    await provisioner.wait_log(r"Waiting for unprovisioned beacon", timeout=_TIMEOUT)
    await provisioner.wait_log(r"Provisioning [0-9a-f]+", timeout=_TIMEOUT)
    await provisioner.wait_log(r"Added node 0x[0-9a-f]+", timeout=_TIMEOUT)
    await provisioner.wait_log(r"Configuring node 0x[0-9a-f]+", timeout=_TIMEOUT)
    await provisioner.wait_log(r"Configuration complete", timeout=_TIMEOUT)
