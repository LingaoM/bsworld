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
"""Python Controller with a dedicated radio worker thread and an H:4 endpoint."""

from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from ..env import Env
from ..runtime.proc import ProcessManager
from .controller import Controller

if TYPE_CHECKING:
    from bscontroller import RadioController
    from bscontroller.hci.transport import H4Server


@dataclass(eq=False, repr=False)
class BSController(Controller):
    max_step_us: int | None = None
    _worker: RadioController | None = field(default=None, init=False, repr=False)
    _endpoint: H4Server | None = field(default=None, init=False, repr=False)
    _task: asyncio.Task | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.max_step_us is not None and self.max_step_us <= 0:
            raise ValueError("max_step_us must be positive")

    async def start(self, pm: ProcessManager, env: Env, *, log_dir: Path) -> None:
        from bscontroller import RadioController
        from bscontroller.hci.transport import H4Server

        if self._worker is not None:
            raise RuntimeError("BSController is already started")
        self.hci_snoop_file = (
            self.hci_snoop_file or log_dir / "bscontroller" / f"hci{self.controller_dev_id}.snoop"
        ).resolve()
        options = {"hci_snoop_file": self.hci_snoop_file}
        if self.max_step_us is not None:
            options["max_step_us"] = self.max_step_us
        self._worker = RadioController(
            f"hci{self.controller_dev_id}",
            self.public_address or (
                f"F0:F1:F2:{(self.controller_dev_id >> 16) & 255:02X}:"
                f"{(self.controller_dev_id >> 8) & 255:02X}:{self.controller_dev_id & 255:02X}"
            ),
            **options,
        )
        self._endpoint = H4Server(self._worker, self.hci_sock)
        try:
            await self._endpoint.__aenter__()
        except BaseException:
            await self._worker.close()
            self._worker = None
            self._endpoint = None
            raise
        # Other Controllers, applications and the framework clock still need
        # to register before a worker can finish its PHY connection.
        self._task = asyncio.create_task(self._run(), name=f"bscontroller:hci{self.controller_dev_id}")

    async def _run(self) -> None:
        await self._worker.start(self.sim_id, self.controller_dev_id)
        await self._worker.terminated

    async def stop(self) -> None:
        if self._task is not None:
            try:
                async with AsyncExitStack() as cleanup:
                    cleanup.push_async_callback(self._endpoint.__aexit__, None, None, None)
                    cleanup.push_async_callback(self._worker.close)
                    self._task.cancel()
                    try:
                        await self._task
                    except asyncio.CancelledError:
                        pass
            finally:
                self._task = None
                self._endpoint = None
                self._worker = None
