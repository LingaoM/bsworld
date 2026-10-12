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
"""Build all BSWorld native dependencies and prebuilt runtimes."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from .runtime_assets import (
        AssetDiscoveryError,
        RuntimeAsset,
        discover_runtime_assets,
        missing_launchers,
        prebuilt_dirs,
        unexpected_launchers,
    )
except ImportError:
    from runtime_assets import (
        AssetDiscoveryError,
        RuntimeAsset,
        discover_runtime_assets,
        missing_launchers,
        prebuilt_dirs,
        unexpected_launchers,
    )

_REPO_ROOT = Path(__file__).resolve().parents[1]


class BuildError(RuntimeError):
    pass


def _run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=_REPO_ROOT, env=env, check=True)


def _require_directory(name: str, path: Path) -> Path:
    path = path.resolve()
    if not path.is_dir():
        raise BuildError(f"{name} directory not found: {path}")
    return path


def _clean_assets(assets: tuple[RuntimeAsset, ...]) -> None:
    for relative in prebuilt_dirs(assets):
        shutil.rmtree(_REPO_ROOT / relative, ignore_errors=True)


def _verify_assets(assets: tuple[RuntimeAsset, ...]) -> None:
    missing = missing_launchers(_REPO_ROOT, assets)
    if missing:
        formatted = "\n".join(f"  - {path}" for path in missing)
        raise BuildError(f"build did not produce the test-declared launchers:\n{formatted}")

    unexpected = unexpected_launchers(_REPO_ROOT, assets)
    if unexpected:
        formatted = "\n".join(f"  - {path}" for path in unexpected)
        raise BuildError(f"build produced undeclared launchers:\n{formatted}")


def build_all(args: argparse.Namespace) -> None:
    nuttx_dir = _require_directory("NuttX", args.nuttx_dir)
    nuttx_apps_dir = _require_directory("nuttx-apps", args.nuttx_apps_dir)
    zephyr_workspace = _require_directory("Zephyr workspace", args.zephyr_workspace)
    bsim_out_dir = args.bsim_out_dir.resolve()
    bsim_components = _REPO_ROOT / "components" / "babblesim" / "components"
    _require_directory("BabbleSim components", bsim_components)
    assets = discover_runtime_assets(_REPO_ROOT)
    _clean_assets(assets)

    env = os.environ.copy()
    python_bin_dir = str(Path(sys.prefix) / "bin")
    env.update(
        {
            "BSIM_OUT_PATH": str(bsim_out_dir),
            "BSIM_COMPONENTS_PATH": str(bsim_components),
            "BSIM_BASE_PATH": str(bsim_components),
            "BSIM_BUILD_FAIL_ASAP": "1",
            "BSWORLD_PYTHON": sys.executable,
            "PATH": f"{python_bin_dir}{os.pathsep}{env.get('PATH', '')}",
        }
    )

    print("==> Building BabbleSim", flush=True)
    _run(
        [
            "make",
            "-C",
            str(_REPO_ROOT / "components" / "babblesim"),
            f"BSIM_OUT_PATH={bsim_out_dir}",
            f"BSIM_COMPONENTS_PATH={bsim_components}",
            f"BSIM_BASE_PATH={bsim_components}",
            "BSIM_BUILD_FAIL_ASAP=1",
            "everything",
        ],
        env=env,
    )

    controller_command = [
        str(_REPO_ROOT / "components" / "bt_virt_controller" / "build.sh"),
        "--zephyr-workspace",
        str(zephyr_workspace),
        "--bsim-out-dir",
        str(bsim_out_dir),
    ]
    if args.skip_source_update:
        controller_command.append("--skip-zephyr-update")
    _run(controller_command, env=env)

    nuttx_command = [
        str(_REPO_ROOT / "tests" / "integration" / "nuttx" / "build.sh"),
        "--nuttx-dir",
        str(nuttx_dir),
        "--nuttx-apps-dir",
        str(nuttx_apps_dir),
        "--bsim-out-dir",
        str(bsim_out_dir),
        "--jobs",
        str(args.jobs),
    ]
    if args.skip_source_update:
        nuttx_command.append("--skip-nuttx-update")
    _run(nuttx_command, env=env)

    _run(
        [
            str(
                _REPO_ROOT
                / "tests"
                / "integration"
                / "zephyr"
                / "samples"
                / "build.sh"
            ),
            "--zephyr-workspace",
            str(zephyr_workspace),
            "--bsim-out-dir",
            str(bsim_out_dir),
            "--skip-zephyr-update",
        ],
        env=env,
    )
    _verify_assets(assets)

    print(f"Built {len(assets)} test-declared runtime(s).")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nuttx-dir", type=Path, required=True)
    parser.add_argument("--nuttx-apps-dir", type=Path, required=True)
    parser.add_argument("--zephyr-workspace", type=Path, required=True)
    parser.add_argument("--bsim-out-dir", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    parser.add_argument(
        "--skip-source-update",
        action="store_true",
        help="use existing source checkouts after validating their pinned revisions",
    )
    args = parser.parse_args()
    if args.jobs <= 0:
        parser.error("--jobs must be a positive integer")
    return args


def main() -> int:
    try:
        build_all(_parse_args())
    except (
        AssetDiscoveryError,
        BuildError,
        OSError,
        subprocess.CalledProcessError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
