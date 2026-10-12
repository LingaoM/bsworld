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
"""Discover release-managed runtimes from BSWorld and test profiles."""

from __future__ import annotations

import hashlib
import importlib.util
import os
import sys
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SOURCE_ROOT = str(_REPO_ROOT / "src")
if _SOURCE_ROOT not in sys.path:
    sys.path.insert(0, _SOURCE_ROOT)

from bsworld.env import virtual_controller_launcher  # noqa: E402


class AssetDiscoveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeAsset:
    launcher: Path
    sources: tuple[str, ...]

    @property
    def prebuilt_dir(self) -> Path:
        parts = self.launcher.parts
        try:
            index = parts.index("prebuilt")
        except ValueError as exc:
            raise AssetDiscoveryError(
                f"runtime launcher is not under a prebuilt directory: {self.launcher}"
            ) from exc
        return Path(*parts[: index + 1])


def _load_module(path: Path, repo_root: Path) -> ModuleType:
    relative = path.relative_to(repo_root).as_posix()
    digest = hashlib.sha256(relative.encode()).hexdigest()[:16]
    name = f"_bsworld_runtime_assets_{digest}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssetDiscoveryError(f"cannot load test profile module: {relative}")

    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(repo_root))
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise AssetDiscoveryError(
            f"cannot import test profile module {relative}: {exc}"
        ) from exc
    finally:
        sys.path.pop(0)
    return module


def _profiles(value: Any, seen: set[int]) -> Iterator[Any]:
    if hasattr(value, "path") and hasattr(value, "name"):
        yield value
        return

    identity = id(value)
    if identity in seen:
        return
    if isinstance(value, Mapping):
        seen.add(identity)
        for item in value.values():
            yield from _profiles(item, seen)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        seen.add(identity)
        for item in value:
            yield from _profiles(item, seen)


def _managed_launcher(path: Path, repo_root: Path) -> Path | None:
    absolute = path if path.is_absolute() else repo_root / path
    try:
        relative = absolute.absolute().relative_to(repo_root.absolute())
    except ValueError:
        return None

    parts = relative.parts
    if "prebuilt" not in parts:
        return None
    if not any(
        parts[index : index + 2] == ("exodus", "bin")
        for index in range(len(parts) - 1)
    ):
        raise AssetDiscoveryError(
            f"prebuilt profile path is not an Exodus launcher: {relative}"
        )
    return relative


def _record(
    discovered: dict[Path, set[str]],
    launcher: Path | None,
    source: str,
) -> None:
    if launcher is not None:
        discovered.setdefault(launcher, set()).add(source)


def discover_runtime_assets(repo_root: Path) -> tuple[RuntimeAsset, ...]:
    """Collect managed launchers from framework paths and test device profiles."""
    repo_root = repo_root.resolve()
    discovered: dict[Path, set[str]] = {}

    controller = virtual_controller_launcher(repo_root).relative_to(repo_root)
    _record(discovered, controller, "bsworld.virtual_controller")

    for path in sorted((repo_root / "tests").glob("**/devices.py")):
        module = _load_module(path, repo_root)
        module_name = (
            path.relative_to(repo_root).with_suffix("").as_posix().replace("/", ".")
        )
        seen_profiles: set[int] = set()
        for variable, value in vars(module).items():
            if variable.startswith("__"):
                continue
            for profile in _profiles(value, set()):
                if id(profile) in seen_profiles:
                    continue
                seen_profiles.add(id(profile))
                source = f"{module_name}.{variable}:{profile.name}"
                _record(
                    discovered,
                    _managed_launcher(profile.path, repo_root),
                    f"{source}.path",
                )

    return tuple(
        RuntimeAsset(launcher=launcher, sources=tuple(sorted(sources)))
        for launcher, sources in sorted(discovered.items())
    )


def prebuilt_dirs(assets: tuple[RuntimeAsset, ...]) -> tuple[Path, ...]:
    return tuple(sorted({asset.prebuilt_dir for asset in assets}))


def missing_launchers(repo_root: Path, assets: tuple[RuntimeAsset, ...]) -> list[Path]:
    return [
        asset.launcher
        for asset in assets
        if not (repo_root / asset.launcher).is_file()
        or not os.access(repo_root / asset.launcher, os.X_OK)
    ]


def discovered_launchers(
    repo_root: Path, assets: tuple[RuntimeAsset, ...]
) -> set[Path]:
    launchers: set[Path] = set()
    for relative in prebuilt_dirs(assets):
        directory = repo_root / relative
        if not directory.is_dir():
            continue
        for launcher in directory.glob("**/exodus/bin/*"):
            if launcher.is_file() or launcher.is_symlink():
                launchers.add(launcher.relative_to(repo_root))
    return launchers


def unexpected_launchers(
    repo_root: Path, assets: tuple[RuntimeAsset, ...]
) -> list[Path]:
    expected = {asset.launcher for asset in assets}
    return sorted(discovered_launchers(repo_root, assets) - expected)


def manifest_data(assets: tuple[RuntimeAsset, ...]) -> dict[str, object]:
    return {
        "schema": 2,
        "runtimes": [
            {
                "launcher": asset.launcher.as_posix(),
                "sources": list(asset.sources),
            }
            for asset in assets
        ],
    }


__all__ = [
    "AssetDiscoveryError",
    "RuntimeAsset",
    "discover_runtime_assets",
    "discovered_launchers",
    "manifest_data",
    "missing_launchers",
    "prebuilt_dirs",
    "unexpected_launchers",
]
