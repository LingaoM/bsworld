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
"""Copy a controller-provided BTSnoop Unix socket stream to an artifact file."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO


@dataclass
class BtsnoopSocketCapture:
    socket_path: Path
    output_path: Path
    _task: asyncio.Task[None] | None = field(default=None, init=False, repr=False)

    async def start(self, *, timeout: float = 5.0) -> None:
        if self._task is not None:
            return
        reader, writer = await asyncio.wait_for(
            asyncio.open_unix_connection(str(self.socket_path)),
            timeout=timeout,
        )
        try:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            fh = open(self.output_path, "wb", buffering=0)  # noqa: SIM115
        except BaseException:
            writer.close()
            await writer.wait_closed()
            raise
        self._task = asyncio.create_task(
            self._copy_stream(reader, writer, fh),
            name=f"btsnoop:{self.socket_path.name}",
        )

    async def stop(self, *, timeout: float = 5.0) -> None:
        task = self._task
        self._task = None
        if task is None:
            return
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
        except TimeoutError:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def _copy_stream(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        fh: BinaryIO,
    ) -> None:
        try:
            while True:
                chunk = await reader.read(65536)
                if not chunk:
                    return
                fh.write(chunk)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionResetError, OSError):
                pass
            fh.close()


__all__ = ["BtsnoopSocketCapture"]
