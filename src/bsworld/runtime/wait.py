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
"""Deadline-based condition-wait helpers."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable


def wait_for(
    pred: Callable[[], bool],
    *,
    timeout: float,
    poll: float = 0.05,
    desc: str = "",
) -> None:
    deadline = time.monotonic() + timeout
    while True:
        if pred():
            return
        if time.monotonic() >= deadline:
            raise TimeoutError(f"timed out after {timeout:.1f}s waiting for {desc or pred}")
        time.sleep(poll)


def wait_for_path(path: Path, timeout: float = 10.0, *, poll: float = 0.05) -> None:
    wait_for(lambda: path.exists() or path.is_symlink(), timeout=timeout, poll=poll, desc=str(path))


def wait_for_paths(paths: list[Path], timeout: float = 10.0, *, poll: float = 0.05) -> None:
    wait_for(
        lambda: all(p.exists() or p.is_symlink() for p in paths),
        timeout=timeout,
        poll=poll,
        desc=", ".join(str(p) for p in paths),
    )
