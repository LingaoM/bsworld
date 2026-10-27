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

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from ..env import Env
from ..runtime.proc import ProcessManager
from .controller import Controller

if TYPE_CHECKING:
    from bscontroller import ControllerConfig, RadioController


@dataclass(eq=False, repr=False)
class BSController(Controller):
    """BSController in a worker thread.

    ``config`` is a ``bscontroller.ControllerConfig`` with this Controller's
    Controller-defined values (buffers, list sizes, limits).
    """

    max_step_us: int | None = None
    config: ControllerConfig | None = None
    _worker: RadioController | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.max_step_us is not None and self.max_step_us <= 0:
            raise ValueError("max_step_us must be positive")
        if self.config is not None:
            from bscontroller import ControllerConfig

            if not isinstance(self.config, ControllerConfig):
                raise TypeError("config must be a bscontroller.ControllerConfig")

    async def start(self, pm: ProcessManager, env: Env, *, log_dir: Path) -> None:
        from bscontroller import RadioController

        if self._worker is not None:
            raise RuntimeError("BSController is already started")
        if self.hci_snoop_file is None:
            raise RuntimeError(
                "hci_snoop_file is assigned when the Controller is allocated"
            )
        name = f"hci{self.controller_dev_id}"
        options = {"hci_snoop_file": self.hci_snoop_file, "hci_socket": self.hci_sock}
        if self.max_step_us is not None:
            options["max_step_us"] = self.max_step_us
        if self.config is not None:
            options["config"] = self.config
        self._worker = RadioController(
            name,
            self.public_address
            or (
                f"F0:F1:F2:{(self.controller_dev_id >> 16) & 255:02X}:"
                f"{(self.controller_dev_id >> 8) & 255:02X}:"
                f"{self.controller_dev_id & 255:02X}"
            ),
            **options,
        )
        try:
            await self._worker.start(self.sim_id, self.controller_dev_id)
        except BaseException:
            try:
                await self._worker.close()
            finally:
                self._worker = None
            raise

    async def stop(self) -> None:
        if self._worker is not None:
            try:
                await self._worker.close()
            finally:
                self._worker = None
