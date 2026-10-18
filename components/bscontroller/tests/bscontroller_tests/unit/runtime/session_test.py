# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

import asyncio
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bscontroller.radio.babblesim import (
    HEADER,
    NEVER,
    TIME,
    WAIT,
    WAIT_END,
)
from bscontroller.runtime.session import BabbleSimClock, BabbleSimSession

requires_runner = pytest.mark.skipif(not hasattr(asyncio, 'Runner'), reason='Controller loops require Python 3.11')

requires_pipe2 = pytest.mark.skipif(not hasattr(os, 'pipe2'), reason='FIFO tests require os.pipe2')


@pytest.mark.asyncio
async def test_session_can_use_existing_host_loop_without_its_own_clock():
    worker = SimpleNamespace(start=AsyncMock(), close=AsyncMock())
    loop = asyncio.get_running_loop()
    async with BabbleSimSession('test', [(0, worker)]) as session:
        assert asyncio.get_running_loop() is loop
        assert session.clock is None and session.loop is None
        worker.start.assert_awaited_once_with('test', 0)
    worker.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_standalone_session_binds_clock_after_startup_barrier(monkeypatch):
    events = []
    worker = SimpleNamespace(
        start=AsyncMock(side_effect=lambda *args: events.append('start')),
        close=AsyncMock(side_effect=lambda: events.append('stop')),
        check=lambda: None,
    )
    session = BabbleSimSession('test', [(0, worker)], clock_dev_id=1)
    session.clock.connection.connect = AsyncMock(side_effect=lambda: events.append('connect'))
    session.clock.connection.wait_sync = lambda *args: events.append('barrier')
    session.clock.connection.close = lambda: events.append('disconnect')
    loop = asyncio.get_running_loop()
    monkeypatch.setattr(loop, 'bind_clock', lambda clock: events.append('bind'), raising=False)
    monkeypatch.setattr(loop, 'unbind_clock', lambda: events.append('unbind'), raising=False)
    async with session:
        assert session.loop is loop
        assert events == ['start', 'connect', 'barrier', 'bind']
    assert events == [
        'start',
        'connect',
        'barrier',
        'bind',
        'unbind',
        'stop',
        'disconnect',
    ]


@pytest.mark.asyncio
async def test_session_start_failure_closes_started_and_unstarted_workers():
    first = SimpleNamespace(start=AsyncMock(), close=AsyncMock())
    second = SimpleNamespace(start=AsyncMock(side_effect=RuntimeError('broken worker')), close=AsyncMock())
    session = BabbleSimSession('test', [(0, first), (1, second)])
    with pytest.raises(RuntimeError, match='broken worker'):
        await session.__aenter__()
    first.close.assert_awaited_once()
    second.close.assert_awaited_once()


def test_session_requires_at_least_one_controller():
    with pytest.raises(ValueError, match='at least one'):
        BabbleSimSession('test', [])


@pytest.mark.asyncio
async def test_session_stops_all_workers_before_releasing_host_grant():
    events = []

    async def close(name, fail=False):
        events.append(name)
        if fail:
            raise RuntimeError('broken worker')

    workers = [
        SimpleNamespace(close=lambda: close('first', True)),
        SimpleNamespace(close=lambda: close('second')),
    ]
    session = BabbleSimSession('test', list(enumerate(workers)), clock_dev_id=2)
    session.loop = SimpleNamespace(unbind_clock=lambda: events.append('unbind'))
    session.clock.connection.close = lambda: events.append('release')
    with pytest.raises(RuntimeError, match='broken worker'):
        await session.__aexit__(None, None, None)
    assert events == ['unbind', 'first', 'second', 'release']


@pytest.mark.asyncio
async def test_host_clock_changes_only_after_its_own_ack(endpoints):
    device, phy = endpoints
    clock = BabbleSimClock(device)

    async def respond():
        assert await phy.receive(12) == HEADER.pack(WAIT) + TIME.pack(1234)
        assert clock.now_us == 0
        await phy.send(HEADER.pack(WAIT_END))

    result, _ = await asyncio.gather(asyncio.to_thread(clock.advance_to_us, 1234), respond())
    assert result == clock.now_us == 1234
    for invalid in (1233, NEVER, -1):
        with pytest.raises(ValueError, match='nondecreasing'):
            clock.advance_to_us(invalid)


def test_session_rejects_duplicate_controller_or_clock_identity():
    with pytest.raises(ValueError, match='distinct'):
        BabbleSimSession('test', [(0, None), (0, None)], clock_dev_id=2)
    with pytest.raises(ValueError, match='distinct'):
        BabbleSimSession('test', [(0, None)], clock_dev_id=0)
