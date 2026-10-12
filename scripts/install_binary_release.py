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
"""Install expanded runtime trees from a BSWorld binary release ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

try:
    from .runtime_assets import (
        AssetDiscoveryError,
        RuntimeAsset,
        discover_runtime_assets,
        manifest_data,
        prebuilt_dirs,
    )
except ImportError:
    from runtime_assets import (
        AssetDiscoveryError,
        RuntimeAsset,
        discover_runtime_assets,
        manifest_data,
        prebuilt_dirs,
    )

_REPO_ROOT = Path(__file__).resolve().parents[1]
_MANIFEST_NAME = "runtime-manifest.json"


class ArchiveError(RuntimeError):
    pass


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_entries(content: str) -> dict[PurePosixPath, str]:
    entries: dict[PurePosixPath, str] = {}
    for line in content.splitlines():
        if not line.strip():
            continue
        try:
            digest, name = line.split(maxsplit=1)
        except ValueError as exc:
            raise ArchiveError(f"invalid checksum line: {line!r}") from exc
        name = name.lstrip("*")
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts:
            raise ArchiveError(f"unsafe checksum path: {name}")
        entries[path] = digest
    return entries


def _safe_archive_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if not path.parts or path.is_absolute() or ".." in path.parts:
        raise ArchiveError(f"unsafe ZIP path: {name}")
    return path


def _validate_link_target(link: PurePosixPath, target: str) -> None:
    target_path = PurePosixPath(target)
    if target_path.is_absolute():
        raise ArchiveError(f"absolute ZIP symlink target: {link} -> {target}")

    resolved: list[str] = []
    for part in (link.parent / target_path).parts:
        if part in ("", "."):
            continue
        if part == "..":
            if not resolved:
                raise ArchiveError(f"escaping ZIP symlink target: {link} -> {target}")
            resolved.pop()
        else:
            resolved.append(part)


def _ensure_parent(destination: Path, relative: PurePosixPath) -> Path:
    parent = destination
    for part in relative.parts[:-1]:
        parent /= part
        if parent.is_symlink():
            raise ArchiveError(f"ZIP member traverses a symlink: {relative}")
        parent.mkdir(exist_ok=True)
    return destination.joinpath(*relative.parts)


def _extract_zip(archive_path: Path, destination: Path) -> None:
    try:
        with zipfile.ZipFile(archive_path) as archive:
            for info in archive.infolist():
                relative = _safe_archive_path(info.filename)
                path = _ensure_parent(destination, relative)
                mode = info.external_attr >> 16
                file_type = stat.S_IFMT(mode)

                if info.is_dir():
                    if path.is_symlink():
                        raise ArchiveError(f"ZIP directory replaces a symlink: {relative}")
                    path.mkdir(exist_ok=True)
                elif file_type == stat.S_IFLNK:
                    target = archive.read(info).decode()
                    _validate_link_target(relative, target)
                    if path.exists() or path.is_symlink():
                        raise ArchiveError(f"duplicate ZIP member: {relative}")
                    path.symlink_to(target)
                elif file_type in (0, stat.S_IFREG):
                    if path.exists() or path.is_symlink():
                        raise ArchiveError(f"duplicate ZIP member: {relative}")
                    with archive.open(info) as source, path.open("wb") as target:
                        shutil.copyfileobj(source, target)
                else:
                    raise ArchiveError(f"unsupported ZIP member type: {relative}")

                permissions = stat.S_IMODE(mode)
                if permissions and not path.is_symlink():
                    path.chmod(permissions)
    except (OSError, UnicodeDecodeError, zipfile.BadZipFile) as exc:
        raise ArchiveError(f"cannot extract {archive_path}: {exc}") from exc


def _find_package_root(stage: Path) -> Path:
    candidates = [path.parent for path in stage.rglob(_MANIFEST_NAME)]
    if len(candidates) != 1:
        raise ArchiveError(f"expected one {_MANIFEST_NAME}, found {len(candidates)}")
    return candidates[0]


def _verify_runtime_manifest(
    package_root: Path, assets: tuple[RuntimeAsset, ...]
) -> None:
    path = package_root / _MANIFEST_NAME
    try:
        packaged = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ArchiveError(f"invalid {_MANIFEST_NAME}: {exc}") from exc
    if packaged != manifest_data(assets):
        raise ArchiveError("prebuilt manifest does not match this BSWorld source tree")


def _verify_checksums(package_root: Path) -> None:
    manifest_path = package_root / "checksums.sha256"
    if not manifest_path.is_file():
        raise ArchiveError("release has no checksums.sha256")
    for relative, expected in _manifest_entries(manifest_path.read_text()).items():
        path = package_root.joinpath(*relative.parts)
        if not path.is_file() or _sha256_file(path) != expected:
            raise ArchiveError(f"checksum mismatch: {relative}")


def _remove(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def _replace_tree(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent)
    )
    try:
        copied = staging / destination.name
        shutil.copytree(source, copied, symlinks=True)
        _remove(destination)
        copied.replace(destination)
    finally:
        _remove(staging)


def install_binary_release(archive: Path, repo_root: Path) -> int:
    archive = archive.resolve()
    repo_root = repo_root.resolve()
    if not archive.is_file() or not zipfile.is_zipfile(archive):
        raise ArchiveError(f"prebuilt release is not a ZIP file: {archive}")
    if not (repo_root / "pyproject.toml").is_file():
        raise ArchiveError(f"not a BSWorld repository root: {repo_root}")
    assets = discover_runtime_assets(repo_root)

    with tempfile.TemporaryDirectory(prefix="bsworld-prebuilt.") as temp:
        stage = Path(temp)
        _extract_zip(archive, stage)
        package_root = _find_package_root(stage)
        _verify_runtime_manifest(package_root, assets)
        _verify_checksums(package_root)

        if any(package_root.rglob("*.tgz")):
            raise ArchiveError("legacy nested Exodus tarballs are not supported")

        for asset in assets:
            launcher = package_root / asset.launcher
            if not launcher.is_file() or not os.access(launcher, os.X_OK):
                raise ArchiveError(f"missing prebuilt launcher: {asset.launcher}")

        for relative in prebuilt_dirs(assets):
            source = package_root / relative
            if not source.is_dir():
                raise ArchiveError(f"missing prebuilt directory: {relative}")
            _replace_tree(source, repo_root / relative)

    return len(assets)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install a BSWorld binary release ZIP into its repository paths.",
    )
    parser.add_argument("archive", type=Path)
    parser.add_argument("--repo-root", type=Path, default=_REPO_ROOT)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        count = install_binary_release(args.archive, args.repo_root)
    except (ArchiveError, AssetDiscoveryError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"Installed {count} test-declared runtime(s) under {args.repo_root.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
