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

import pytest

from bsworld.runtime import wait as wait_mod
from bsworld.runtime.wait import wait_for, wait_for_path, wait_for_paths


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
