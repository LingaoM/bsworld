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

import asyncio
import time
from collections.abc import Callable, Sequence
from pathlib import Path


def _present(paths: Sequence[Path]) -> bool:
    return all(path.exists() or path.is_symlink() for path in paths)


def _describe(paths: Sequence[Path]) -> str:
    return ", ".join(str(path) for path in paths)


def _remaining(pred: Callable[[], bool], deadline: float, timeout: float, desc: str) -> float:
    """Time left before the deadline, or 0.0 once the predicate holds.

    Raises TimeoutError when the deadline passes without the predicate
    becoming true, so the sync and async loops share one expiry rule.
    """
    if pred():
        return 0.0
    left = deadline - time.monotonic()
    if left <= 0:
        raise TimeoutError(f"timed out after {timeout:.1f}s waiting for {desc}")
    return left


def wait_for(
    pred: Callable[[], bool],
    *,
    timeout: float,
    poll: float = 0.05,
    desc: str = "",
) -> None:
    deadline = time.monotonic() + timeout
    described = desc or str(pred)
    while True:
        left = _remaining(pred, deadline, timeout, described)
        if left == 0.0:
            return
        time.sleep(min(poll, left))


def wait_for_paths(paths: Sequence[Path], timeout: float = 10.0, *, poll: float = 0.05) -> None:
    wait_for(lambda: _present(paths), timeout=timeout, poll=poll, desc=_describe(paths))


def wait_for_path(path: Path, timeout: float = 10.0, *, poll: float = 0.05) -> None:
    wait_for_paths([path], timeout=timeout, poll=poll)


async def wait_for_paths_async(paths: Sequence[Path], timeout: float = 10.0, *, poll: float = 0.05) -> None:
    """Wait for startup paths while allowing other event-loop tasks to run."""
    deadline = time.monotonic() + timeout
    described = _describe(paths)
    while True:
        left = _remaining(lambda: _present(paths), deadline, timeout, described)
        if left == 0.0:
            return
        await asyncio.sleep(min(poll, left))
