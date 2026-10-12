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
"""Line-oriented command input for launched processes."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .proc import Proc


class ProcessShell:
    """Small wrapper around a child process stdin pipe.

    The object is intentionally platform-neutral. Zephyr shell, NuttX NSH, or
    another future firmware console can all consume line-oriented commands from
    stdin when the corresponding process enables shell input.
    """

    def __init__(self, *, label: str, enabled: bool = False) -> None:
        self.label = label
        self.enabled = enabled
        self._proc: Proc | None = None

    def attach(self, proc: "Proc") -> None:
        self._proc = proc

    def detach(self) -> None:
        self._proc = None

    async def run(self, command: str) -> None:
        """Send one command line to the child process."""
        self.send(command)

    async def run_many(self, commands: Sequence[str]) -> None:
        """Send multiple command lines to the child process."""
        self.send_many(commands)

    def send(self, command: str) -> None:
        """Synchronously send one command line to the child process."""
        if command.endswith("\n"):
            self.write(command)
        else:
            self.write(f"{command}\n")

    def send_many(self, commands: Sequence[str]) -> None:
        if not commands:
            return
        stdin = self._stdin()
        chunks = [
            command if command.endswith("\n") else f"{command}\n"
            for command in commands
        ]
        payload = "".join(chunks).encode()
        try:
            stdin.write(payload)
            stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise RuntimeError(f"{self.label}: shell input is closed") from exc

    def write(self, data: str | bytes) -> None:
        stdin = self._stdin()
        payload = data.encode() if isinstance(data, str) else data
        try:
            stdin.write(payload)
            stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise RuntimeError(f"{self.label}: shell input is closed") from exc

    def flush(self) -> None:
        stdin = self._stdin()
        try:
            stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise RuntimeError(f"{self.label}: shell input is closed") from exc

    def _stdin(self):
        if not self.enabled:
            raise RuntimeError(f"{self.label}: shell input is not enabled")
        if self._proc is None or self._proc.popen.stdin is None:
            raise RuntimeError(f"{self.label}: shell input is not available")
        return self._proc.popen.stdin


__all__ = ["ProcessShell"]
