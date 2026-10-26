# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import errno
import os
import struct
from pathlib import Path

import pytest

from bsworld.runtime.scheduler import BsimClock, babblesim


@pytest.fixture
def fifo_clock(tmp_path):
    sim_dir = tmp_path / "sim"
    sim_dir.mkdir()
    request_path = sim_dir / "2G4.d4.dtp"
    response_path = sim_dir / "2G4.d4.ptd"
    os.mkfifo(request_path)
    os.mkfifo(response_path)
    request_fd = os.open(request_path, os.O_RDWR | os.O_NONBLOCK)
    response_fd = os.open(response_path, os.O_RDWR | os.O_NONBLOCK)
    clock = BsimClock(sim_dir=sim_dir, phy_id="2G4", dev_id=4)
    try:
        yield clock, request_fd, response_fd
    finally:
        clock.close()
        os.close(request_fd)
        os.close(response_fd)


def test_clock_connect_creates_native_format_lock_and_nonblocking_fds(
    fifo_clock,
) -> None:
    clock, _, _ = fifo_clock
    clock.connect()
    lock = clock.sim_dir / "2G4.d4.lock"
    pid, start_time = lock.read_text().splitlines()
    assert pid == str(os.getpid())
    assert (
        start_time == Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()[19]
    )
    assert not os.get_blocking(clock._read_fd)
    assert not os.get_blocking(clock._write_fd)
    assert clock.now_us == 0
    clock.connect()
    assert lock.read_text().splitlines() == [pid, start_time]


def test_clock_advance_sends_packed_absolute_target_and_waits_for_ack(
    fifo_clock, monkeypatch
) -> None:
    clock, request_fd, response_fd = fifo_clock
    clock.connect()
    os.write(response_fd, struct.pack("=I", 0x81))
    read = os.read

    def check_time(fd, size):
        if fd == clock._read_fd:
            assert clock.now_us == 0
        return read(fd, size)

    monkeypatch.setattr(babblesim.os, "read", check_time)
    assert clock.advance_to_us(5_000) == 5_000
    assert read(request_fd, 100) == struct.pack("=IQ", 0x01, 5_000)
    assert len(struct.pack("=IQ", 0x01, 5_000)) == 12
    assert clock.advance_to_us(5_000) == 5_000
    assert clock.advance_to_us(1_000) == 5_000
    with pytest.raises(BlockingIOError):
        read(request_fd, 100)


def test_clock_advance_requires_connection(fifo_clock) -> None:
    clock, _, _ = fifo_clock
    with pytest.raises(RuntimeError, match="not connected"):
        clock.advance_to_us(1_000)
    clock.connect()
    clock.close()
    with pytest.raises(RuntimeError, match="not connected"):
        clock.advance_to_us(1_000)


def test_clock_synchronize_waits_for_ack_without_advancing_time(fifo_clock) -> None:
    clock, request_fd, response_fd = fifo_clock
    with pytest.raises(RuntimeError, match="not connected"):
        clock.synchronize()
    clock.connect()
    os.write(response_fd, struct.pack("=I", 0x81))
    clock.synchronize()
    assert clock.now_us == 0
    assert os.read(request_fd, 100) == struct.pack("=IQ", 0x01, 0)
    os.write(response_fd, struct.pack("=I", 0x81))
    clock.advance_to_us(1_000)
    os.read(request_fd, 100)
    os.write(response_fd, struct.pack("=I", 0x81))
    clock.synchronize()
    assert clock.now_us == 1_000
    assert os.read(request_fd, 100) == struct.pack("=IQ", 0x01, 1_000)


def test_clock_synchronize_timeout_releases_connection(fifo_clock) -> None:
    clock, _, _ = fifo_clock
    clock.connect()
    clock.step_timeout = 0
    with pytest.raises(TimeoutError, match="timed out"):
        clock.synchronize()
    assert clock.now_us == 0
    assert clock._write_fd is None
    assert not (clock.sim_dir / "2G4.d4.lock").exists()


@pytest.mark.parametrize("target", [-1, (1 << 64) - 1, 1 << 64])
def test_clock_rejects_invalid_time(fifo_clock, target) -> None:
    clock, request_fd, _ = fifo_clock
    clock.connect()
    with pytest.raises(ValueError, match="finite uint64"):
        clock.advance_to_us(target)
    with pytest.raises(BlockingIOError):
        os.read(request_fd, 100)


def test_clock_rejects_lock_conflict_without_removing_another_clients_lock(
    fifo_clock,
) -> None:
    clock, _, response_fd = fifo_clock
    clock.connect()
    lock = clock.sim_dir / "2G4.d4.lock"
    original = lock.read_bytes()
    other = BsimClock(sim_dir=clock.sim_dir, phy_id="2G4", dev_id=4)
    with pytest.raises(FileExistsError):
        other.connect(timeout=0)
    other.close()
    assert lock.read_bytes() == original
    os.write(response_fd, struct.pack("=I", 0x81))
    assert clock.advance_to_us(1_000) == 1_000


@pytest.mark.parametrize("fifos_exist", [False, True])
def test_clock_connection_times_out_without_phy_and_releases_lock(
    tmp_path, fifos_exist
) -> None:
    if fifos_exist:
        os.mkfifo(tmp_path / "2G4.d0.ptd")
        os.mkfifo(tmp_path / "2G4.d0.dtp")
    clock = BsimClock(sim_dir=tmp_path, phy_id="2G4", dev_id=0)
    with pytest.raises(TimeoutError, match="did not connect"):
        clock.connect(timeout=0)
    assert not (tmp_path / "2G4.d0.lock").exists()
    assert clock._read_fd is None
    assert clock._write_fd is None


def test_clock_connection_detects_phy_exit_without_waiting(tmp_path) -> None:
    clock = BsimClock(sim_dir=tmp_path, phy_id="2G4", dev_id=0, phy_alive=lambda: False)
    with pytest.raises(RuntimeError, match="PHY exited"):
        clock.connect()
    assert not (tmp_path / "2G4.d0.lock").exists()


@pytest.mark.parametrize("suffix", ["ptd", "dtp"])
def test_clock_rejects_regular_files_without_deleting_them(fifo_clock, suffix) -> None:
    clock, _, _ = fifo_clock
    path = clock.sim_dir / f"2G4.d4.{suffix}"
    path.unlink()
    path.write_text("not a FIFO")
    with pytest.raises(RuntimeError, match="not a FIFO"):
        clock.connect(timeout=0)
    assert path.read_text() == "not a FIFO"
    assert not (clock.sim_dir / "2G4.d4.lock").exists()


def test_clock_connection_permission_error_releases_lock(
    fifo_clock, monkeypatch
) -> None:
    clock, _, _ = fifo_clock

    def deny(path, flags):
        raise PermissionError(errno.EACCES, "denied")

    monkeypatch.setattr(clock, "_open_fifo", deny)
    with pytest.raises(PermissionError):
        clock.connect()
    assert not (clock.sim_dir / "2G4.d4.lock").exists()


@pytest.mark.parametrize(
    "header, message", [(0xFFFF, "disconnected"), (0x82, "invalid.*response")]
)
def test_clock_bad_response_disconnects_without_advancing_time(
    fifo_clock, header, message
) -> None:
    clock, _, response_fd = fifo_clock
    clock.connect()
    os.write(response_fd, struct.pack("=I", header))
    with pytest.raises(RuntimeError, match=message):
        clock.advance_to_us(1_000)
    assert clock.now_us == 0
    assert not (clock.sim_dir / "2G4.d4.lock").exists()


def test_clock_response_timeout_disconnects_without_advancing_time(fifo_clock) -> None:
    clock, _, _ = fifo_clock
    clock.connect()
    clock.step_timeout = 0
    with pytest.raises(TimeoutError, match="timed out"):
        clock.advance_to_us(1_000)
    assert clock.now_us == 0
    assert clock._write_fd is None


def test_clock_handles_short_reads_and_writes(fifo_clock, monkeypatch) -> None:
    clock, request_fd, response_fd = fifo_clock
    clock.connect()
    os.write(response_fd, struct.pack("=I", 0x81))
    read, write = os.read, os.write
    monkeypatch.setattr(babblesim.os, "read", lambda fd, size: read(fd, min(size, 2)))
    monkeypatch.setattr(babblesim.os, "write", lambda fd, packet: write(fd, packet[:2]))
    assert clock.advance_to_us(1_000) == 1_000
    assert read(request_fd, 100) == struct.pack("=IQ", 0x01, 1_000)


@pytest.mark.parametrize("operation", ["read", "write"])
def test_clock_retries_eagain(fifo_clock, monkeypatch, operation) -> None:
    clock, _, response_fd = fifo_clock
    clock.connect()
    os.write(response_fd, struct.pack("=I", 0x81))
    original = getattr(os, operation)
    calls = 0

    def retry(fd, data):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise BlockingIOError(errno.EAGAIN, "try again")
        return original(fd, data)

    monkeypatch.setattr(babblesim.os, operation, retry)
    assert clock.advance_to_us(1_000) == 1_000
    assert calls >= 2


@pytest.mark.parametrize("error", [OSError("poll failed"), KeyboardInterrupt()])
def test_clock_poll_failure_or_interrupt_disconnects(
    fifo_clock, monkeypatch, error
) -> None:
    clock, _, _ = fifo_clock
    clock.connect()

    def fail(*args):
        raise error

    monkeypatch.setattr(babblesim.select, "select", fail)
    with pytest.raises(type(error)):
        clock.advance_to_us(1_000)
    assert clock._write_fd is None
    assert not (clock.sim_dir / "2G4.d4.lock").exists()


@pytest.mark.parametrize("operation", ["eof", "broken_pipe", "zero_write"])
def test_clock_transport_failure_disconnects(
    fifo_clock, monkeypatch, operation
) -> None:
    clock, _, response_fd = fifo_clock
    clock.connect()
    os.write(response_fd, struct.pack("=I", 0x81))
    if operation == "eof":
        monkeypatch.setattr(babblesim.os, "read", lambda *args: b"")
    elif operation == "zero_write":
        monkeypatch.setattr(babblesim.os, "write", lambda *args: 0)
    else:

        def broken(*args):
            raise BrokenPipeError(errno.EPIPE, "closed")

        monkeypatch.setattr(babblesim.os, "write", broken)
    with pytest.raises(RuntimeError, match="disconnected|no progress"):
        clock.advance_to_us(1_000)
    assert clock.now_us == 0
    assert clock._write_fd is None


def test_clock_close_notifies_phy_and_is_idempotent(fifo_clock) -> None:
    clock, request_fd, _ = fifo_clock
    clock.close()
    clock.connect()
    clock.close()
    clock.close()
    assert os.read(request_fd, 100) == struct.pack("=I", 0xFFFF)
    assert not (clock.sim_dir / "2G4.d4.lock").exists()
