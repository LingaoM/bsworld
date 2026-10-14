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

from pathlib import Path
from types import SimpleNamespace

import pytest

from bsworld.compile import bsim as bsim_compile
from bsworld.compile import hci_virt as hci_virt_compile


def _bsim_env(tmp_path: Path) -> SimpleNamespace:
    bsim_dir = tmp_path / "build" / "babblesim" / "bsim"
    return SimpleNamespace(
        babblesim_root=tmp_path / "components" / "babblesim",
        babblesim_components_dir=tmp_path / "components" / "babblesim" / "components",
        bsim_dir=bsim_dir,
        bsim_bin_dir=bsim_dir / "bin",
    )


def _write_bsim_outputs(env: SimpleNamespace) -> None:
    for rel in bsim_compile._OUTPUTS:
        path = env.bsim_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("output\n")
        if rel.startswith("bin/"):
            path.chmod(0o755)


def _hci_env(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        hci_virt_bin=(
            tmp_path
            / "components"
            / "bt_virt_controller"
            / "build"
            / "bt_virt_controller"
        ),
    )


def _write_controller(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n")
    path.chmod(0o755)


def test_bsim_check_ready_accepts_runtime_without_source(tmp_path) -> None:
    env = _bsim_env(tmp_path)
    _write_bsim_outputs(env)
    assert not env.babblesim_root.exists()

    bsim_compile.check_ready(env)


def test_bsim_check_ready_rejects_missing_radio_module(tmp_path) -> None:
    env = _bsim_env(tmp_path)
    _write_bsim_outputs(env)
    (env.bsim_dir / "lib" / "lib_2G4Channel_multiatt.so").unlink()

    with pytest.raises(SystemExit) as exc:
        bsim_compile.check_ready(env)

    assert exc.value.code == 15


def test_bsim_check_ready_rejects_missing_outputs(tmp_path) -> None:
    env = _bsim_env(tmp_path)
    _write_bsim_outputs(env)
    (env.bsim_bin_dir / "bs_2G4_phy_v1").unlink()

    with pytest.raises(SystemExit) as exc:
        bsim_compile.check_ready(env)

    assert exc.value.code == 15


def test_bsim_check_ready_rejects_non_executable_phy(tmp_path) -> None:
    env = _bsim_env(tmp_path)
    _write_bsim_outputs(env)
    (env.bsim_bin_dir / "bs_2G4_phy_v1").chmod(0o644)

    with pytest.raises(SystemExit) as exc:
        bsim_compile.check_ready(env)

    assert exc.value.code == 15


def test_hci_virt_check_ready_accepts_native_controller(tmp_path) -> None:
    env = _hci_env(tmp_path)
    _write_controller(env.hci_virt_bin)

    hci_virt_compile.check_ready(env)
    launcher = hci_virt_compile.controller_bin(env)

    assert launcher.is_file()
    assert launcher.parent.name == "build"
    assert launcher.stat().st_mode & 0o111


def test_hci_virt_check_ready_rejects_missing_launcher(tmp_path) -> None:
    env = _hci_env(tmp_path)

    with pytest.raises(SystemExit) as exc:
        hci_virt_compile.check_ready(env)

    assert exc.value.code == 15


def test_hci_virt_check_ready_rejects_unset_path() -> None:
    with pytest.raises(SystemExit) as exc:
        hci_virt_compile.check_ready(SimpleNamespace(hci_virt_bin=None))
    assert exc.value.code == 15


def test_hci_virt_check_ready_rejects_non_executable(tmp_path) -> None:
    env = _hci_env(tmp_path)
    _write_controller(env.hci_virt_bin)
    env.hci_virt_bin.chmod(0o644)
    with pytest.raises(SystemExit) as exc:
        hci_virt_compile.check_ready(env)
    assert exc.value.code == 15


def test_bsim_check_ready_rejects_unset_path() -> None:
    with pytest.raises(SystemExit) as exc:
        bsim_compile.check_ready(SimpleNamespace(bsim_dir=None))
    assert exc.value.code == 15
