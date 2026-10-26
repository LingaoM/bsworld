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
"""The registration flow every integration suite shares."""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.integration.applications import add_application, require_artifact

from bsworld.devices import BSController, ZephyrController
from bsworld.devices.layout import AppSlot
from bsworld.env import Env
from bsworld.topology import BluetoothTopology

_GUIDE = "docs/writing-tests.md"


def _env(tmp_path: Path) -> Env:
    return Env(
        out_tag="run-test",
        run_uid="uid",
        out_dir=tmp_path / "out",
        log_dir=tmp_path / "out" / "log",
        hci_virt_bin=tmp_path / "components" / "hci",
        bsim_dir=tmp_path / "bsim",
        bsim_bin_dir=tmp_path / "bsim" / "bin",
        bs_state_dir=tmp_path / "state",
    )


def _executable(tmp_path: Path, name: str = "firmware") -> Path:
    binary = tmp_path / name
    binary.write_text("native output")
    binary.chmod(0o755)
    return binary


def _argv(binary: Path, slot: AppSlot) -> list[str | Path]:
    return [binary, f"--dev={slot.dev_id}", f"--sim={slot.sim_id}", slot.hci_sock]


def test_registered_application_receives_its_own_slot(tmp_path, monkeypatch) -> None:
    binary = _executable(tmp_path)
    monkeypatch.setenv("BSWORLD_TEST_BIN", str(binary))
    topo = BluetoothTopology(_env(tmp_path), "sim0", tmp_path / "log")

    process = add_application(
        topo,
        binary_env="BSWORLD_TEST_BIN",
        guide=_GUIDE,
        argv=_argv,
        label="device",
        controller_address="c0:ff:ee:00:00:09",
        log_subdir="devices/device",
    )

    assert process.controller.public_address == "C0:FF:EE:00:00:09"
    slot = topo.bsim.plan_devices().application_slot(process.controller)
    assert [str(part) for part in process._resolve_command(slot)] == [
        str(binary),
        "--dev=1",
        "--sim=sim0",
        str(tmp_path / "state" / "sim0" / "hci0.sock"),
    ]


def test_registration_skips_before_touching_the_topology(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("BSWORLD_TEST_BIN", raising=False)
    topo = BluetoothTopology(_env(tmp_path), "sim0", tmp_path / "log")

    with pytest.raises(pytest.skip.Exception, match="BSWORLD_TEST_BIN"):
        add_application(
            topo,
            binary_env="BSWORLD_TEST_BIN",
            guide=_GUIDE,
            argv=_argv,
            label="device",
        )

    assert topo.bsim.controllers == []
    assert topo.processes == []


def test_registration_inherits_the_topology_controller_default(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("BSWORLD_TEST_BIN", str(_executable(tmp_path)))
    topo = BluetoothTopology(
        _env(tmp_path), "sim0", tmp_path / "log", default_controller_type=BSController
    )

    inherited = add_application(
        topo, binary_env="BSWORLD_TEST_BIN", guide=_GUIDE, argv=_argv, label="inherited"
    )
    overridden = add_application(
        topo,
        binary_env="BSWORLD_TEST_BIN",
        guide=_GUIDE,
        argv=_argv,
        label="overridden",
        controller_type=ZephyrController,
    )

    assert isinstance(inherited.controller, BSController)
    assert isinstance(overridden.controller, ZephyrController)


def test_a_prebuilt_binary_bypasses_the_environment_lookup(
    tmp_path, monkeypatch
) -> None:
    binary = _executable(tmp_path)
    monkeypatch.delenv("BSWORLD_TEST_BIN", raising=False)
    topo = BluetoothTopology(_env(tmp_path), "sim0", tmp_path / "log")

    process = add_application(
        topo, binary=binary, argv=_argv, label="device", shell=True
    )

    assert process.shell.enabled is True
    slot = topo.bsim.plan_devices().application_slot(process.controller)
    assert process._resolve_command(slot)[0] == binary


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"binary": Path("/bin/true"), "binary_env": "BSWORLD_TEST_BIN"},
    ],
)
def test_exactly_one_binary_source_is_required(tmp_path, kwargs) -> None:
    topo = BluetoothTopology(_env(tmp_path), "sim0", tmp_path / "log")

    with pytest.raises(TypeError, match="exactly one of binary or binary_env"):
        add_application(topo, argv=_argv, label="device", guide=_GUIDE, **kwargs)


def test_an_environment_selected_binary_requires_its_guide(tmp_path) -> None:
    topo = BluetoothTopology(_env(tmp_path), "sim0", tmp_path / "log")

    with pytest.raises(TypeError, match="requires guide"):
        add_application(topo, binary_env="BSWORLD_TEST_BIN", argv=_argv, label="device")


@pytest.mark.parametrize("executable", [False, True])
def test_artifacts_are_resolved_on_every_call(
    tmp_path, monkeypatch, executable
) -> None:
    artifact = tmp_path / "artifact"
    artifact.write_text("output")
    monkeypatch.setenv("BSWORLD_TEST_BIN", str(artifact))

    if executable:
        with pytest.raises(pytest.skip.Exception, match="compiled executable"):
            require_artifact("BSWORLD_TEST_BIN", guide=_GUIDE)
        artifact.chmod(0o755)
    assert (
        require_artifact("BSWORLD_TEST_BIN", guide=_GUIDE, executable=executable)
        == artifact
    )

    # Reselecting the artifact takes effect without reimporting any profile.
    monkeypatch.setenv("BSWORLD_TEST_BIN", str(tmp_path / "missing"))
    with pytest.raises(pytest.skip.Exception, match="BSWORLD_TEST_BIN"):
        require_artifact("BSWORLD_TEST_BIN", guide=_GUIDE, executable=executable)
