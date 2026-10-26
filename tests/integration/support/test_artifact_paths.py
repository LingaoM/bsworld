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
from __future__ import annotations

import pytest
from tests.integration.nuttx.common import NuttXProcessProfile
from tests.integration.nuttx.common import require_binaries as require_nuttx_binaries
from tests.integration.qemu.common import _artifact
from tests.integration.zephyr.shell.devices import add_zephyr_shell

from bsworld.devices import BSController, ZephyrController


def test_nuttx_profiles_follow_exports_without_staging(monkeypatch, tmp_path) -> None:
    profile = NuttXProcessProfile("nuttx_device", "BSWORLD_NUTTX_BTSAK_BIN")
    require = require_nuttx_binaries

    monkeypatch.delenv(profile.binary_env, raising=False)
    with pytest.raises(pytest.skip.Exception, match=profile.binary_env):
        require([profile])

    binary = tmp_path / "upstream project" / "original executable"
    binary.parent.mkdir()
    binary.write_text("native output")
    monkeypatch.setenv(profile.binary_env, str(binary))
    with pytest.raises(pytest.skip.Exception, match=profile.binary_env):
        require([profile])

    binary.chmod(0o755)
    require([profile])
    assert profile.path == binary
    assert list(binary.parent.iterdir()) == [binary]

    # Switching the selected executable does not require reimporting profiles.
    monkeypatch.setenv(profile.binary_env, str(tmp_path / "missing executable"))
    with pytest.raises(pytest.skip.Exception, match=profile.binary_env):
        require([profile])


@pytest.mark.parametrize("mesh", [False, True], ids=["bluetooth", "mesh"])
def test_zephyr_shell_follows_exports_without_staging(
    monkeypatch, tmp_path, topo, mesh
) -> None:
    binary_env = "BSWORLD_ZEPHYR_MESH_SHELL_BIN" if mesh else "BSWORLD_ZEPHYR_SHELL_BIN"

    def register():
        return add_zephyr_shell(
            topo,
            name="device",
            address="C0:FF:EE:41:00:02",
            mesh=mesh,
            controller_type=ZephyrController,
        )

    monkeypatch.delenv(binary_env, raising=False)
    with pytest.raises(pytest.skip.Exception, match=binary_env):
        register()

    binary = tmp_path / "upstream project" / "original executable"
    binary.parent.mkdir()
    binary.write_text("native output")
    monkeypatch.setenv(binary_env, str(binary))
    with pytest.raises(pytest.skip.Exception, match=binary_env):
        register()

    binary.chmod(0o755)
    topo.default_controller_type = BSController
    device = register()
    assert isinstance(device.controller, ZephyrController)
    assert device.shell.enabled is True
    slot = topo.bsim.plan_devices().application_slot(device.controller)
    assert device._resolve_command(slot) == [
        binary,
        f"-s={slot.sim_id}",
        f"-p={slot.phy_id}",
        f"-d={slot.dev_id}",
        "-mro=1000",
        f"--bt-dev={slot.hci_sock}",
    ]
    assert list(binary.parent.iterdir()) == [binary]

    monkeypatch.setenv(binary_env, str(tmp_path / "missing executable"))
    with pytest.raises(pytest.skip.Exception, match=binary_env):
        register()


@pytest.mark.parametrize(
    "variable", ["BSWORLD_QEMU_BIN", "BSWORLD_QEMU_KERNEL", "BSWORLD_QEMU_ROOTFS"]
)
def test_qemu_requires_explicit_outputs(monkeypatch, tmp_path, variable) -> None:
    monkeypatch.setenv(variable, "")
    with pytest.raises(pytest.skip.Exception, match=variable):
        _artifact(variable)

    artifact = tmp_path / "upstream output"
    artifact.write_text("output")
    monkeypatch.setenv(variable, str(artifact))
    assert _artifact(variable) == artifact

    if variable == "BSWORLD_QEMU_BIN":
        with pytest.raises(pytest.skip.Exception, match=variable):
            _artifact(variable, executable=True)
        artifact.chmod(0o755)
        assert _artifact(variable, executable=True) == artifact
