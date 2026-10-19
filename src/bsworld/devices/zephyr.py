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
"""Zephyr Controller running in a native simulator process."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from ..compile import hci_virt
from ..env import Env
from ..runtime.proc import Proc, ProcessManager
from .controller import Controller


@dataclass(eq=False, repr=False)
class ZephyrController(Controller):
    _process: Proc | None = field(default=None, init=False, repr=False)
    _pm: ProcessManager | None = field(default=None, init=False, repr=False)

    async def start(self, pm: ProcessManager, env: Env, *, log_dir: Path) -> None:
        if self._process is not None:
            raise RuntimeError("Zephyr Controller is already started")
        binary = hci_virt.controller_bin(env)
        controller_log_dir = log_dir / "bt_virt_controller"
        self.hci_snoop_file = (
            self.hci_snoop_file or controller_log_dir / f"hci{self.controller_dev_id}.snoop"
        ).resolve()
        self.hci_snoop_file.parent.mkdir(parents=True, exist_ok=True)
        argv = [
            binary,
            f"-s={self.sim_id}",
            f"-d={self.controller_dev_id}",
            f"-hci-socket={self.hci_sock}",
            f"-btsnoop-file={self.hci_snoop_file}",
        ]
        if self.public_address is not None:
            argv.append(f"-bd-addr={self.public_address}")
        self._process = pm.spawn(
            f"bt_virt_controller_hci{self.controller_dev_id}",
            argv,
            cwd=binary.parent,
            log_dir=controller_log_dir,
        )
        self._pm = pm

    async def stop(self) -> None:
        if self._process is not None:
            await asyncio.to_thread(self._pm.stop, self._process)
            self._process = None
            self._pm = None
