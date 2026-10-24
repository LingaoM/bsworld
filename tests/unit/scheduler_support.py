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

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from bsworld.runtime.scheduler import PYTEST_MAX_STEP_US, BsimEventLoop

T = TypeVar("T")


class ManualClock:
    def __init__(
        self,
        *,
        before_advance: Callable[[int, int], None] | None = None,
    ) -> None:
        self.now_us = 0
        self.before_advance = before_advance
        self.targets_us: list[int] = []

    def advance_to_us(self, target_us: int) -> int:
        if target_us < self.now_us:
            raise ValueError("a discrete clock cannot move backwards")
        if target_us == self.now_us:
            return self.now_us
        if self.before_advance is not None:
            self.before_advance(self.now_us, target_us)
        self.targets_us.append(target_us)
        self.now_us = target_us
        return self.now_us


def run_on_clock(
    awaitable: Awaitable[T],
    *,
    clock: ManualClock,
    max_step_us: int = PYTEST_MAX_STEP_US,
) -> T:
    async def run_bound() -> T:
        try:
            return await awaitable
        finally:
            loop = asyncio.get_running_loop()
            assert isinstance(loop, BsimEventLoop)
            loop.unbind_clock()

    def loop_factory() -> BsimEventLoop:
        loop = BsimEventLoop(max_step_us)
        loop.bind_clock(clock)
        asyncio.set_event_loop(loop)
        return loop

    return asyncio.run(run_bound(), loop_factory=loop_factory)
