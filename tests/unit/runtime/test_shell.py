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
"""Unit tests for process shell command input."""

from __future__ import annotations

import io

import pytest

from bsworld.runtime.shell import ProcessShell


class _CountingBytesIO(io.BytesIO):
    def __init__(self) -> None:
        super().__init__()
        self.flush_count = 0

    def flush(self) -> None:
        self.flush_count += 1
        super().flush()


class _Popen:
    def __init__(self, stdin: object | None) -> None:
        self.stdin = stdin


class _Proc:
    def __init__(self, stdin: object | None) -> None:
        self.popen = _Popen(stdin)


async def test_process_shell_run_writes_line_to_stdin() -> None:
    stdin = io.BytesIO()
    shell = ProcessShell(label="dev0", enabled=True)
    shell.attach(_Proc(stdin))

    await shell.run("ifup bnep0")
    await shell.run("blecent\n")

    assert stdin.getvalue() == b"ifup bnep0\nblecent\n"


async def test_process_shell_run_many_is_noop_for_empty_commands() -> None:
    shell = ProcessShell(label="dev0", enabled=False)

    await shell.run_many(())


async def test_process_shell_run_many_flushes_once() -> None:
    stdin = _CountingBytesIO()
    shell = ProcessShell(label="dev0", enabled=True)
    shell.attach(_Proc(stdin))

    await shell.run_many(("ifup bnep0", "blecent"))

    assert stdin.getvalue() == b"ifup bnep0\nblecent\n"
    assert stdin.flush_count == 1


def test_process_shell_rejects_disabled_input() -> None:
    shell = ProcessShell(label="dev0", enabled=False)

    with pytest.raises(RuntimeError, match="shell input is not enabled"):
        shell.send("ifup bnep0")


def test_process_shell_rejects_unattached_input() -> None:
    shell = ProcessShell(label="dev0", enabled=True)

    with pytest.raises(RuntimeError, match="shell input is not available"):
        shell.send("ifup bnep0")
