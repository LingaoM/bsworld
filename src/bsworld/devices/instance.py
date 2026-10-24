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
"""Application process instance managed by a BluetoothTopology."""
from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from ..runtime.pipe import LogCapture
from ..runtime.shell import ProcessShell
from .layout import AppSlot

if TYPE_CHECKING:
    from ..runtime.proc import ProcessManager
    from .controller import Controller


class ProcessInstance:
    """One Application process connected to one Virtual Controller."""

    def __init__(
        self,
        *,
        command: list[str | Path] | Callable[[AppSlot], list[str | Path]],
        controller: "Controller",
        label: str,
        shell: bool = False,
        log_subdir: Path | str | None = None,
    ) -> None:
        if not callable(command) and not command:
            raise ValueError("process command must not be empty")
        self._command_factory = command
        self.controller = controller
        self.label = label
        self.shell = ProcessShell(label=label, enabled=shell)
        self.log_subdir = Path(log_subdir) if log_subdir is not None else Path()
        self._pipe: LogCapture | None = None

    def start(
        self,
        pm: "ProcessManager",
        log_dir: Path,
        slot: AppSlot,
    ) -> None:
        command = self._resolve_command(slot)
        executable = Path(command[0])
        if not executable.is_file():
            from ..log import die

            die(f"{self.label}: binary missing: {executable}", code=2)

        dev_log_dir = log_dir / self.log_subdir
        log_path = dev_log_dir / f"{self.label}.log"
        self._pipe = LogCapture.open(log_path)

        try:
            proc = pm.spawn(
                self.label,
                command,
                cwd=dev_log_dir,
                log_dir=dev_log_dir,
                stdin=subprocess.PIPE if self.shell.enabled else None,
                stdout=self._pipe.write_fd,
                stderr=self._pipe.write_fd,
                log_fh=self._pipe.log_fh,
            )
            self.shell.attach(proc)
        except Exception:
            self.shell.detach()
            self.stop_capture()
            raise

        from ..log import log

        log(f"{self.label}: started (pid={proc.pid})")

    def _resolve_command(self, slot: AppSlot) -> list[str | Path]:
        command = self._command_factory(slot) if callable(self._command_factory) else self._command_factory
        if not command:
            raise ValueError("process command must not be empty")
        return list(command)

    def stop_capture(self) -> None:
        self.shell.detach()
        if self._pipe is None:
            return
        self._pipe.stop()
        self._pipe = None

    async def wait_log(self, pattern: str, *, timeout: float = 30.0) -> str:
        if self._pipe is None:
            raise RuntimeError(f"{self.label}: not started yet")
        return await self._pipe.wait_log(pattern, timeout=timeout)


__all__ = ["ProcessInstance"]
