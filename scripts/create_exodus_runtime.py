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
"""Build an expanded Exodus runtime directory without creating a tarball."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

_EXODUS_VERSION = "2.0.4"


class BuildError(RuntimeError):
    pass


def _remove(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def create_exodus_runtime(
    executable: Path,
    output: Path,
    launcher: str,
    *,
    strip_binary: bool = False,
) -> Path:
    try:
        installed_version = version("exodus-bundler")
    except PackageNotFoundError as exc:
        raise BuildError(
            f"exodus-bundler {_EXODUS_VERSION} is required; "
            f"install it with: python3.12 -m pip install exodus-bundler=={_EXODUS_VERSION}"
        ) from exc
    if installed_version != _EXODUS_VERSION:
        raise BuildError(
            f"unsupported exodus-bundler version {installed_version}; expected {_EXODUS_VERSION}"
        )

    from exodus_bundler.bundling import create_unpackaged_bundle

    executable = executable.resolve()
    output = output.resolve()
    if not executable.is_file():
        raise BuildError(f"executable not found: {executable}")

    output.parent.mkdir(parents=True, exist_ok=True)
    bundle_root: Path | None = None
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        with tempfile.TemporaryDirectory(prefix="bsworld-package.") as package_dir:
            packaged_executable = Path(package_dir) / executable.name
            shutil.copy2(executable, packaged_executable)
            packaged_executable.chmod(packaged_executable.stat().st_mode | 0o111)
            if strip_binary:
                subprocess.run(["strip", packaged_executable], check=True)

            bundle_root = Path(
                create_unpackaged_bundle(
                    [str(packaged_executable)],
                    rename=[launcher],
                )
            )
            shutil.move(str(bundle_root), staging / "exodus")
            bundle_root = None

        launcher_path = staging / "exodus" / "bin" / launcher
        if not launcher_path.is_file() or not os.access(launcher_path, os.X_OK):
            raise BuildError(f"Exodus launcher was not generated: {launcher_path}")

        _remove(output)
        staging.replace(output)
        return output / "exodus" / "bin" / launcher
    finally:
        if bundle_root is not None:
            _remove(bundle_root)
        _remove(staging)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build an expanded Exodus runtime tree.",
    )
    parser.add_argument("executable", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--launcher", required=True)
    parser.add_argument("--strip", action="store_true", dest="strip_binary")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        launcher = create_exodus_runtime(
            args.executable,
            args.output,
            args.launcher,
            strip_binary=args.strip_binary,
        )
    except (BuildError, OSError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"Built {launcher}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
