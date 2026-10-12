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
from __future__ import annotations

import os
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from scripts.runtime_assets import RuntimeAsset, discover_runtime_assets

_ROOT = Path(__file__).parents[2]


def _init_git(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "revision-marker").write_text("test\n")
    subprocess.run(["git", "init", "-q", path], check=True)
    subprocess.run(["git", "-C", path, "add", "revision-marker"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            path,
            "-c",
            "user.name=BSWorld Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-q",
            "-m",
            "test revision",
        ],
        check=True,
    )


def _write_test_profiles(repo: Path) -> None:
    devices = repo / "tests" / "integration" / "example" / "devices.py"
    devices.parent.mkdir(parents=True)
    devices.write_text(
        """from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class ProcessProfile:
    name: str
    path: Path

PREBUILT = Path(__file__).resolve().parent / "prebuilt"
DEVICE = PREBUILT / "device" / "exodus" / "bin" / "device"

DEVICE_A = ProcessProfile(name="device_a", path=DEVICE)
DEVICE_B = ProcessProfile(name="device_b", path=DEVICE)
EXTERNAL_TOOL = ProcessProfile(name="external", path=Path("/bin/true"))
DEVICE_GROUP = [DEVICE_A, DEVICE_B]
"""
    )


def _create_runtime_trees(repo: Path, assets: tuple[RuntimeAsset, ...]) -> None:
    for asset in assets:
        launcher = repo / asset.launcher
        target = launcher.parent.parent / "bundles" / "test-bundle" / "app"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("#!/bin/sh\n")
        target.chmod(0o755)
        launcher.parent.mkdir(parents=True, exist_ok=True)
        launcher.symlink_to(os.path.relpath(target, launcher.parent))


@pytest.fixture
def build_workspace(tmp_path: Path) -> dict[str, Path]:
    repo = tmp_path / "source"
    _init_git(repo)
    (repo / "pyproject.toml").write_text("[project]\nname = 'bsworld'\n")
    (repo / "LICENSE").write_text("license\n")
    (repo / "THIRD_PARTY_NOTICES.md").write_text("notices\n")
    chinese_notices = repo / "docs" / "zh-CH" / "THIRD_PARTY_NOTICES.md"
    chinese_notices.parent.mkdir(parents=True)
    chinese_notices.write_text("notices\n")
    _write_test_profiles(repo)
    _create_runtime_trees(repo, discover_runtime_assets(repo))

    babblesim = repo / "components" / "babblesim" / "base"
    nuttx = tmp_path / "nuttx"
    nuttx_apps = tmp_path / "nuttx-apps"
    zephyr_workspace = tmp_path / "zephyrproject"
    zephyr = zephyr_workspace / "zephyr"
    for source in (babblesim, nuttx, nuttx_apps, zephyr):
        _init_git(source)

    return {
        "repo": repo,
        "nuttx": nuttx,
        "nuttx_apps": nuttx_apps,
        "zephyr_workspace": zephyr_workspace,
        "bsim_out": tmp_path / "bsim",
    }


def _package_command(workspace: dict[str, Path], output: Path) -> list[object]:
    return [
        sys.executable,
        _ROOT / "scripts" / "create_binary_release.py",
        "--output",
        output,
        "--repo-root",
        workspace["repo"],
        "--nuttx-dir",
        workspace["nuttx"],
        "--nuttx-apps-dir",
        workspace["nuttx_apps"],
        "--zephyr-workspace",
        workspace["zephyr_workspace"],
        "--bsim-out-dir",
        workspace["bsim_out"],
        "--source-date-epoch",
        "946684800",
    ]


def test_create_exodus_runtime_creates_runnable_tree(tmp_path: Path) -> None:
    output = tmp_path / "prebuilt" / "true"

    subprocess.run(
        [
            sys.executable,
            _ROOT / "scripts" / "create_exodus_runtime.py",
            "/bin/true",
            "--launcher",
            "test-app",
            "--output",
            output,
        ],
        check=True,
    )

    launcher = output / "exodus" / "bin" / "test-app"
    assert launcher.is_file()
    subprocess.run([launcher], check=True)


def test_runtime_assets_are_discovered_from_test_profiles(
    build_workspace: dict[str, Path],
) -> None:
    assets = discover_runtime_assets(build_workspace["repo"])

    assert len(assets) == 2
    assert assets[0].launcher == Path(
        "components/bt_virt_controller/prebuilt/bt_virt_controller/"
        "exodus/bin/bt_virt_controller"
    )
    device = next(asset for asset in assets if "prebuilt/device" in asset.launcher.as_posix())
    assert len(device.sources) == 2
    assert all(source.endswith(".path") for source in device.sources)


def test_create_and_install_binary_release_zip(
    tmp_path: Path, build_workspace: dict[str, Path]
) -> None:
    archive = tmp_path / "bsworld-prebuilt-v1.0.0.zip"
    subprocess.run(_package_command(build_workspace, archive), check=True)

    with zipfile.ZipFile(archive) as packaged:
        assert "runtime-manifest.json" in packaged.namelist()
        controller = next(
            info
            for info in packaged.infolist()
            if info.filename.endswith("exodus/bin/bt_virt_controller")
        )
        assert stat.S_IFMT(controller.external_attr >> 16) == stat.S_IFLNK

    destination = tmp_path / "destination"
    destination.mkdir()
    (destination / "pyproject.toml").write_text("[project]\nname = 'bsworld'\n")
    _write_test_profiles(destination)
    subprocess.run(
        [
            sys.executable,
            _ROOT / "scripts" / "install_binary_release.py",
            archive,
            "--repo-root",
            destination,
        ],
        check=True,
    )

    for asset in discover_runtime_assets(build_workspace["repo"]):
        launcher = destination / asset.launcher
        assert launcher.is_symlink()
        subprocess.run([launcher], check=True)


def test_create_binary_release_directory_for_ci(
    tmp_path: Path, build_workspace: dict[str, Path]
) -> None:
    package = tmp_path / "bsworld-prebuilt-v1.0.0"
    subprocess.run(_package_command(build_workspace, package), check=True)

    assert (package / "runtime-manifest.json").is_file()
    assert (package / "checksums.sha256").is_file()
    for asset in discover_runtime_assets(build_workspace["repo"]):
        assert (package / asset.launcher).is_symlink()


def test_create_binary_release_rejects_nested_tarball(
    tmp_path: Path, build_workspace: dict[str, Path]
) -> None:
    first = discover_runtime_assets(build_workspace["repo"])[0]
    legacy = build_workspace["repo"] / first.prebuilt_dir / "legacy.tgz"
    legacy.write_bytes(b"legacy")

    result = subprocess.run(
        _package_command(build_workspace, tmp_path / "release.zip"),
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 2
    assert "obsolete nested archives found" in result.stderr


def test_install_binary_release_rejects_nested_tarball(
    tmp_path: Path, build_workspace: dict[str, Path]
) -> None:
    archive = tmp_path / "release.zip"
    subprocess.run(_package_command(build_workspace, archive), check=True)
    with zipfile.ZipFile(archive, "a") as packaged:
        packaged.writestr(
            "components/bt_virt_controller/prebuilt/legacy.tgz",
            b"legacy",
        )

    destination = tmp_path / "destination"
    destination.mkdir()
    (destination / "pyproject.toml").write_text("[project]\nname = 'bsworld'\n")
    _write_test_profiles(destination)
    result = subprocess.run(
        [
            sys.executable,
            _ROOT / "scripts" / "install_binary_release.py",
            archive,
            "--repo-root",
            destination,
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 2
    assert "legacy nested Exodus tarballs are not supported" in result.stderr
