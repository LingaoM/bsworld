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
"""Unit tests for ProcessManager — process lifecycle, cleanup, signal handling."""
from __future__ import annotations

import signal
import subprocess
from unittest.mock import Mock

import pytest

from bsworld.deps import BSWorldSetupError
from bsworld.runtime import proc as proc_mod
from bsworld.runtime.proc import Proc, ProcessManager


def test_spawn_reports_a_missing_executable(tmp_path) -> None:
    pm = ProcessManager()
    with pytest.raises(BSWorldSetupError, match="missing executable"):
        pm.spawn("ghost", [tmp_path / "does-not-exist"], cwd=tmp_path, log_dir=tmp_path / "log")


def test_spawn_reports_a_missing_working_directory(tmp_path) -> None:
    exe = tmp_path / "sh"
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755)
    pm = ProcessManager()
    with pytest.raises(BSWorldSetupError, match="cwd not found"):
        pm.spawn("proc", [exe], cwd=tmp_path / "nope", log_dir=tmp_path / "log")


def test_spawn_launches_process_and_writes_log(tmp_path) -> None:
    pm = ProcessManager()
    log_dir = tmp_path / "log"
    p = pm.spawn(
        "echoer",
        ["/bin/sh", "-c", "echo hello-world"],
        cwd=tmp_path,
        log_dir=log_dir,
    )
    try:
        assert isinstance(p, Proc)
        assert p.pid > 0
        p.popen.wait(timeout=5)
        assert p.returncode() == 0
        assert not p.alive()
        assert (log_dir / "echoer.log").read_text().strip() == "hello-world"
    finally:
        pm.cleanup()


def test_alive_list_reports_only_running_processes(tmp_path) -> None:
    pm = ProcessManager()
    short = pm.spawn("short", ["/bin/sh", "-c", "true"], cwd=tmp_path, log_dir=tmp_path / "log")
    long = pm.spawn("long", ["/bin/sh", "-c", "sleep 30"], cwd=tmp_path, log_dir=tmp_path / "log")
    try:
        short.popen.wait(timeout=5)
        alive = pm.alive_list()
        assert long in alive
        assert short not in alive
    finally:
        pm.cleanup()


def test_cleanup_kills_running_processes(tmp_path) -> None:
    pm = ProcessManager()
    p = pm.spawn("sleeper", ["/bin/sh", "-c", "sleep 30"], cwd=tmp_path, log_dir=tmp_path / "log")
    assert p.alive()

    pm.cleanup()

    assert not p.alive()
    assert pm.procs == []


def test_cleanup_dumps_tail_for_unexpectedly_exited_process(tmp_path, monkeypatch) -> None:
    logs: list[tuple[str, str]] = []
    warns: list[str] = []
    monkeypatch.setattr(proc_mod, "log", lambda msg, *, tag="bsworld": logs.append((tag, msg)))
    monkeypatch.setattr(proc_mod, "warn", lambda msg: warns.append(msg))

    pm = ProcessManager()
    p = pm.spawn(
        "crasher",
        ["/bin/sh", "-c", "echo boom >&2; exit 3"],
        cwd=tmp_path,
        log_dir=tmp_path / "log",
    )
    p.popen.wait(timeout=5)

    pm.cleanup()

    assert any("exited unexpectedly (rc=3)" in w for w in warns)
    assert any("boom" in msg for _tag, msg in logs)


def test_dump_tail_handles_missing_log_file(tmp_path, monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(proc_mod, "log", lambda msg, *, tag="bsworld": calls.append(msg))
    pm = ProcessManager()
    fake = Proc(name="x", popen=None, log_path=tmp_path / "absent.log", log_fh=None)

    pm._dump_tail(fake, lines=5)

    assert calls == []


def test_kill_session_falls_back_to_os_kill_on_permission_error(monkeypatch) -> None:
    events: list[tuple[str, int, int]] = []

    def fake_killpg(pid, sig):
        events.append(("killpg", pid, sig))
        raise PermissionError

    def fake_kill(pid, sig):
        events.append(("kill", pid, sig))

    monkeypatch.setattr(proc_mod.os, "killpg", fake_killpg)
    monkeypatch.setattr(proc_mod.os, "kill", fake_kill)

    ProcessManager._kill_session(123, signal.SIGTERM)

    assert events == [("killpg", 123, signal.SIGTERM), ("kill", 123, signal.SIGTERM)]


def test_kill_session_ignores_missing_process(monkeypatch) -> None:
    def fake_killpg(pid, sig):
        raise ProcessLookupError

    monkeypatch.setattr(proc_mod.os, "killpg", fake_killpg)
    # Should not raise.
    ProcessManager._kill_session(999, signal.SIGKILL)


def test_install_signal_handlers_is_idempotent(monkeypatch) -> None:
    previous = {sig: object() for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    current = dict(previous)
    installed: list[int] = []

    def fake_signal(sig, handler):  # noqa: ANN001
        installed.append(sig)
        current[sig] = handler

    monkeypatch.setattr(proc_mod.signal, "getsignal", current.__getitem__)
    monkeypatch.setattr(proc_mod.signal, "signal", fake_signal)
    pm = ProcessManager()

    pm.install_signal_handlers()
    first = list(installed)
    pm.install_signal_handlers()

    assert pm._signals_installed is True
    assert installed == first  # second call is a no-op
    assert set(first) == {signal.SIGINT, signal.SIGTERM, signal.SIGHUP}

    pm.restore_signal_handlers()

    assert pm._signals_installed is False
    assert current == previous


def test_cleanup_is_noop_without_processes() -> None:
    pm = ProcessManager()
    pm.cleanup()  # should not raise
    assert pm.procs == []


def test_stop_releases_only_the_selected_process(tmp_path):
    pm = ProcessManager()
    first = pm.spawn("first", ["/bin/sleep", "30"], cwd=tmp_path, log_dir=tmp_path)
    second = pm.spawn("second", ["/bin/sleep", "30"], cwd=tmp_path, log_dir=tmp_path)
    try:
        pm.stop(first)
        pm.stop(first)
        assert not first.alive()
        assert first.log_fh.closed
        assert second.alive()
        assert pm.procs == [second]
    finally:
        pm.cleanup()


@pytest.mark.parametrize("method", ["stop", "cleanup"])
def test_process_reaping_reports_errors_and_releases_bookkeeping(tmp_path, monkeypatch, method):
    warnings = []
    monkeypatch.setattr(proc_mod, "warn", warnings.append)
    popen = Mock()
    popen.poll.return_value = 0
    popen.wait.side_effect = subprocess.TimeoutExpired("child", 5)
    log_fh = Mock()
    log_fh.close.side_effect = OSError("log close failed")
    proc = Proc("child", popen, tmp_path / "child.log", log_fh)
    pm = ProcessManager(procs=[proc])

    if method == "stop":
        pm.stop(proc)
    else:
        pm.cleanup()

    log_fh.close.assert_called_once()
    assert warnings == [
        "child: process did not exit after SIGKILL",
        "child: failed to close log file: log close failed",
    ]
    assert pm.procs == []
