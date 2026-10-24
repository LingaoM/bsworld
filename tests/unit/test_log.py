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
"""Unit tests for the logging helpers and Die exception."""
from __future__ import annotations

import io

import pytest

from bsworld import log as log_mod


@pytest.fixture(autouse=True)
def _reset_sinks():
    log_mod.close_log_file()
    yield
    log_mod.close_log_file()


def test_log_writes_to_stdout_and_file_sink(capsys, tmp_path) -> None:
    log_path = tmp_path / "bsworld.log"
    log_mod.open_log_file(log_path)

    log_mod.log("hello")
    log_mod.close_log_file()

    out = capsys.readouterr().out
    assert "[bsworld] hello" in out
    assert "[bsworld] hello" in log_path.read_text()


def test_log_uses_a_custom_tag(capsys) -> None:
    log_mod.log("started", tag="mydev")
    out = capsys.readouterr().out
    assert "[mydev] started" in out


def test_warn_and_err_write_to_stderr_and_sinks(capsys, tmp_path) -> None:
    log_path = tmp_path / "bsworld.log"
    log_mod.open_log_file(log_path)

    log_mod.warn("careful")
    log_mod.err("broken")
    log_mod.close_log_file()

    captured = capsys.readouterr()
    assert "careful" in captured.err
    assert "broken" in captured.err
    # Tee'd lines are plain (no ANSI) regardless of terminal wrapping.
    content = log_path.read_text()
    assert "[WARN] careful" in content
    assert "[ERROR] broken" in content


def test_tee_without_sinks_does_not_raise(capsys) -> None:
    log_mod.log("no sinks")
    assert "no sinks" in capsys.readouterr().out


def test_close_log_file_is_idempotent(tmp_path) -> None:
    log_mod.open_log_file(tmp_path / "bsworld.log")
    log_mod.close_log_file()
    log_mod.close_log_file()


def test_wrap_adds_ansi_only_when_enabled(monkeypatch) -> None:
    class Tty(io.StringIO):
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr(log_mod.sys, "stderr", Tty())
    assert log_mod._wrap("31", "x") == "\033[31mx\033[0m"
    monkeypatch.setattr(log_mod.sys, "stderr", io.StringIO())
    assert log_mod._wrap("31", "x") == "x"


def test_err_reports_without_exiting_the_interpreter(capsys) -> None:
    # Setup failures raise BSWorldSetupError; logging never terminates pytest.
    log_mod.err("fatal thing")
    assert "fatal thing" in capsys.readouterr().err
    assert not hasattr(log_mod, "die")
    assert not hasattr(log_mod, "Die")
