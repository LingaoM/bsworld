#!/usr/bin/env python3
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
"""Create a BSWorld binary release directory or ZIP archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

try:
    from .runtime_assets import (
        AssetDiscoveryError,
        RuntimeAsset,
        discover_runtime_assets,
        manifest_data,
        missing_launchers,
        prebuilt_dirs,
        unexpected_launchers,
    )
except ImportError:
    from runtime_assets import (
        AssetDiscoveryError,
        RuntimeAsset,
        discover_runtime_assets,
        manifest_data,
        missing_launchers,
        prebuilt_dirs,
        unexpected_launchers,
    )

_REPO_ROOT = Path(__file__).resolve().parents[1]
_MANIFEST_NAME = "runtime-manifest.json"


class PackageError(RuntimeError):
    pass


def _remove(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def _git(repo: Path, *args: str) -> str:
    try:
        return subprocess.run(
            ["git", "-C", repo, *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except subprocess.CalledProcessError as exc:
        raise PackageError(f"cannot read Git metadata from {repo}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _payload_files(stage: Path) -> list[Path]:
    return sorted(
        path
        for path in stage.rglob("*")
        if path.name != "checksums.sha256" and (path.is_file() or path.is_symlink())
    )


def _validate_runtimes(repo_root: Path, assets: tuple[RuntimeAsset, ...]) -> None:
    missing = missing_launchers(repo_root, assets)
    if missing:
        formatted = "\n".join(f"  - {path}" for path in missing)
        raise PackageError(f"missing prebuilt launchers:\n{formatted}")

    unexpected = unexpected_launchers(repo_root, assets)
    if unexpected:
        formatted = "\n".join(f"  - {path}" for path in unexpected)
        raise PackageError(f"undeclared prebuilt launchers:\n{formatted}")

    nested_archives = [
        path.relative_to(repo_root)
        for relative in prebuilt_dirs(assets)
        for path in (repo_root / relative).rglob("*.tgz")
    ]
    if nested_archives:
        formatted = "\n".join(f"  - {path}" for path in nested_archives)
        raise PackageError(f"obsolete nested archives found:\n{formatted}")


def _build_info(
    repo_root: Path,
    nuttx_dir: Path,
    nuttx_apps_dir: Path,
    zephyr_workspace: Path,
    bsim_out_dir: Path,
) -> str:
    values = {
        "bsworld_commit": _git(repo_root, "rev-parse", "HEAD"),
        "babblesim_base_commit": _git(
            repo_root / "components" / "babblesim" / "base", "rev-parse", "HEAD"
        ),
        "nuttx_commit": _git(nuttx_dir, "rev-parse", "HEAD"),
        "nuttx_apps_commit": _git(nuttx_apps_dir, "rev-parse", "HEAD"),
        "zephyr_commit": _git(
            zephyr_workspace / "zephyr", "rev-parse", "HEAD"
        ),
        "bsim_out_path": str(bsim_out_dir.resolve()),
    }
    return "".join(f"{key}={value}\n" for key, value in values.items())


def _populate_stage(
    stage: Path,
    *,
    assets: tuple[RuntimeAsset, ...],
    repo_root: Path,
    nuttx_dir: Path,
    nuttx_apps_dir: Path,
    zephyr_workspace: Path,
    bsim_out_dir: Path,
) -> None:
    _validate_runtimes(repo_root, assets)

    for relative in prebuilt_dirs(assets):
        source = repo_root / relative
        destination = stage / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination, symlinks=True)

    shutil.copy2(repo_root / "LICENSE", stage / "LICENSE")
    shutil.copy2(repo_root / "THIRD_PARTY_NOTICES.md", stage / "THIRD_PARTY_NOTICES.md")
    chinese_notices = stage / "docs" / "zh-CH" / "THIRD_PARTY_NOTICES.md"
    chinese_notices.parent.mkdir(parents=True)
    shutil.copy2(
        repo_root / "docs" / "zh-CH" / "THIRD_PARTY_NOTICES.md",
        chinese_notices,
    )
    (stage / _MANIFEST_NAME).write_text(
        json.dumps(manifest_data(assets), indent=2, sort_keys=True) + "\n"
    )
    (stage / "build-info.txt").write_text(
        _build_info(
            repo_root,
            nuttx_dir,
            nuttx_apps_dir,
            zephyr_workspace,
            bsim_out_dir,
        )
    )

    files = _payload_files(stage)
    (stage / "checksums.sha256").write_text(
        "".join(
            f"{_sha256(path)}  {path.relative_to(stage).as_posix()}\n"
            for path in files
        )
    )


def _zip_datetime(epoch: int) -> tuple[int, int, int, int, int, int]:
    minimum_zip_epoch = 315532800
    return time.gmtime(max(epoch, minimum_zip_epoch))[:6]


def _write_zip(stage: Path, output: Path, epoch: int) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
    )
    os.close(fd)
    temporary = Path(temporary_name)
    timestamp = _zip_datetime(epoch)
    try:
        with zipfile.ZipFile(
            temporary,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for path in sorted(stage.rglob("*")):
                relative = path.relative_to(stage).as_posix()
                mode = path.lstat().st_mode
                if path.is_symlink():
                    info = zipfile.ZipInfo(relative, timestamp)
                    info.create_system = 3
                    info.external_attr = mode << 16
                    archive.writestr(info, os.readlink(path).encode())
                elif path.is_dir():
                    info = zipfile.ZipInfo(f"{relative}/", timestamp)
                    info.create_system = 3
                    info.external_attr = mode << 16
                    archive.writestr(info, b"")
                elif path.is_file():
                    info = zipfile.ZipInfo(relative, timestamp)
                    info.create_system = 3
                    info.external_attr = mode << 16
                    info.compress_type = zipfile.ZIP_DEFLATED
                    with path.open("rb") as source, archive.open(info, "w") as target:
                        shutil.copyfileobj(source, target)

        _remove(output)
        temporary.replace(output)
    finally:
        _remove(temporary)


def create_binary_release(
    output: Path,
    *,
    repo_root: Path,
    nuttx_dir: Path,
    nuttx_apps_dir: Path,
    zephyr_workspace: Path,
    bsim_out_dir: Path,
    source_date_epoch: int,
) -> tuple[Path, int]:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    assets = discover_runtime_assets(repo_root)
    stage = Path(tempfile.mkdtemp(prefix=".bsworld-prebuilt.", dir=output.parent))
    try:
        _populate_stage(
            stage,
            assets=assets,
            repo_root=repo_root.resolve(),
            nuttx_dir=nuttx_dir.resolve(),
            nuttx_apps_dir=nuttx_apps_dir.resolve(),
            zephyr_workspace=zephyr_workspace.resolve(),
            bsim_out_dir=bsim_out_dir.resolve(),
        )
        if output.suffix == ".zip":
            _write_zip(stage, output, source_date_epoch)
        else:
            _remove(output)
            stage.replace(output)
        return output, len(assets)
    finally:
        _remove(stage)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=_REPO_ROOT)
    parser.add_argument("--nuttx-dir", type=Path, required=True)
    parser.add_argument("--nuttx-apps-dir", type=Path, required=True)
    parser.add_argument("--zephyr-workspace", type=Path, required=True)
    parser.add_argument("--bsim-out-dir", type=Path, required=True)
    parser.add_argument("--source-date-epoch", type=int)
    args = parser.parse_args()
    if args.source_date_epoch is None:
        args.source_date_epoch = int(
            _git(args.repo_root.resolve(), "show", "-s", "--format=%ct", "HEAD")
        )
    return args


def main() -> int:
    args = _parse_args()
    try:
        output, count = create_binary_release(
            args.output,
            repo_root=args.repo_root,
            nuttx_dir=args.nuttx_dir,
            nuttx_apps_dir=args.nuttx_apps_dir,
            zephyr_workspace=args.zephyr_workspace,
            bsim_out_dir=args.bsim_out_dir,
            source_date_epoch=args.source_date_epoch,
        )
    except (
        AssetDiscoveryError,
        PackageError,
        OSError,
        ValueError,
        zipfile.BadZipFile,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"Packaged {count} test-declared runtime(s) in {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
