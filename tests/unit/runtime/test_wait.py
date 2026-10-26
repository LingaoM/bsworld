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
"""Unit tests for deadline-based wait helpers."""

from __future__ import annotations

import asyncio

import pytest

from bsworld.runtime import wait as wait_mod
from bsworld.runtime.wait import (
    wait_for,
    wait_for_path,
    wait_for_paths,
    wait_for_paths_async,
)


def test_wait_for_returns_when_predicate_true_immediately() -> None:
    wait_for(lambda: True, timeout=1.0)


def test_wait_for_polls_until_predicate_true(monkeypatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(wait_mod.time, "sleep", lambda s: sleeps.append(s))
    state = {"n": 0}

    def pred() -> bool:
        state["n"] += 1
        return state["n"] >= 3

    wait_for(pred, timeout=1.0, poll=0.01)

    assert state["n"] == 3
    assert sleeps  # slept at least once while waiting


def test_wait_for_raises_timeout(monkeypatch) -> None:
    times = iter([0.0, 0.0, 100.0])
    monkeypatch.setattr(wait_mod.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(wait_mod.time, "sleep", lambda s: None)

    with pytest.raises(TimeoutError, match="waiting for my-thing"):
        wait_for(lambda: False, timeout=1.0, desc="my-thing")


def test_wait_for_path_detects_existing_file(tmp_path) -> None:
    f = tmp_path / "ready"
    f.write_text("x")
    wait_for_path(f, timeout=1.0)


def test_wait_for_path_times_out_for_missing_file(tmp_path, monkeypatch) -> None:
    times = iter([0.0, 0.0, 100.0])
    monkeypatch.setattr(wait_mod.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(wait_mod.time, "sleep", lambda s: None)

    with pytest.raises(TimeoutError):
        wait_for_path(tmp_path / "never", timeout=1.0)


def test_wait_for_paths_detects_all_present(tmp_path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.write_text("")
    b.write_text("")
    wait_for_paths([a, b], timeout=1.0)


async def test_async_path_wait_allows_other_tasks_to_create_paths(
    tmp_path, monkeypatch
):
    paths = [tmp_path / "first", tmp_path / "second"]

    def unexpected_executor(*args, **kwargs):
        raise AssertionError("path readiness must not use an executor thread")

    async def create_paths():
        for path in paths:
            await asyncio.sleep(0)
            path.touch()

    monkeypatch.setattr(
        asyncio.get_running_loop(), "run_in_executor", unexpected_executor
    )
    producer = asyncio.create_task(create_paths())
    try:
        await wait_for_paths_async(paths, timeout=1, poll=0.001)
        await producer
    finally:
        producer.cancel()
        await asyncio.gather(producer, return_exceptions=True)
    assert all(path.exists() for path in paths)


async def test_async_path_wait_times_out_with_missing_path(tmp_path):
    missing = tmp_path / "missing.sock"
    with pytest.raises(TimeoutError, match="missing.sock"):
        await wait_for_paths_async([missing], timeout=0.001)


async def test_async_path_wait_can_be_cancelled(tmp_path):
    task = asyncio.create_task(wait_for_paths_async([tmp_path / "missing.sock"]))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
