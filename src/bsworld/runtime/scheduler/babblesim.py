# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Python client for BabbleSim's FIFO clock protocol."""

from __future__ import annotations

import errno
import os
import select
import stat
import struct
import time
from collections.abc import Callable
from contextlib import ExitStack
from pathlib import Path

# bs_pc_base_types.h sends native-endian uint32 headers and packed uint64 times.
_HEADER = struct.Struct("=I")
_WAIT = struct.Struct("=IQ")
_MSG_WAIT = 0x01
_MSG_WAIT_END = 0x81
_MSG_DISCONNECT = 0xFFFF


class BsimClock:
    """Register pytest as a PHY participant and wait for absolute targets."""

    def __init__(
        self,
        *,
        sim_dir: Path,
        phy_id: str,
        dev_id: int,
        phy_alive: Callable[[], bool] | None = None,
        step_timeout: float = 180.0,
    ) -> None:
        self.sim_dir = sim_dir
        self.phy_id = phy_id
        self.dev_id = dev_id
        self.phy_alive = phy_alive
        self.step_timeout = step_timeout
        prefix = sim_dir / f"{phy_id}.d{dev_id}"
        self._read_path = Path(f"{prefix}.ptd")
        self._write_path = Path(f"{prefix}.dtp")
        self._lock_path = Path(f"{prefix}.lock")
        self._read_fd: int | None = None
        self._write_fd: int | None = None
        self._resources = ExitStack()
        self._now_us = 0

    @property
    def now_us(self) -> int:
        return self._now_us

    def _open_fifo(self, path: Path, flags: int) -> int:
        fd = os.open(path, flags | os.O_NONBLOCK | os.O_CLOEXEC)
        self._resources.callback(os.close, fd)
        if not stat.S_ISFIFO(os.fstat(fd).st_mode):
            raise RuntimeError(f"BabbleSim communication path is not a FIFO: {path}")
        return fd

    def connect(self, *, timeout: float = 30.0) -> None:
        """Wait for PHY-created FIFOs and connect in the native handshake order."""
        if self._write_fd is not None:
            return
        deadline = time.monotonic() + timeout
        try:
            self._register_device()
            self._connect_fifos(deadline)
        except BaseException:
            self.close()
            raise
        self._now_us = 0

    def _register_device(self) -> None:
        self.sim_dir.mkdir(parents=True, exist_ok=True)
        with self._lock_path.open("x") as lock:
            self._resources.callback(self._lock_path.unlink, missing_ok=True)
            # BabbleSim checks PID and /proc start time when inspecting locks.
            start_time = (
                Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()[19]
            )
            lock.write(f"{os.getpid()}\n{start_time}\n")

    def _connect_fifos(self, deadline: float) -> None:
        while True:
            if self.phy_alive is not None and not self.phy_alive():
                raise RuntimeError("BabbleSim PHY exited before clock connection")
            try:
                if self._read_fd is None:
                    self._read_fd = self._open_fifo(self._read_path, os.O_RDONLY)
                self._write_fd = self._open_fifo(self._write_path, os.O_WRONLY)
                return
            except OSError as exc:
                if exc.errno not in (errno.ENOENT, errno.ENXIO):
                    raise
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    f"BabbleSim clock device {self.dev_id} did not connect"
                )
            time.sleep(min(0.01, remaining))

    def _wait_io(self, fd: int, deadline: float, *, write: bool = False) -> None:
        remaining = max(0.0, deadline - time.monotonic())
        readable, writable, _ = select.select(
            [] if write else [fd],
            [fd] if write else [],
            [],
            remaining,
        )
        if not readable and not writable:
            raise TimeoutError("timed out waiting for BabbleSim PHY")

    def _send(self, packet: bytes, deadline: float) -> None:
        while packet:
            try:
                written = os.write(self._write_fd, packet)
            except BlockingIOError:
                self._wait_io(self._write_fd, deadline, write=True)
                continue
            except BrokenPipeError as exc:
                raise RuntimeError(
                    "BabbleSim PHY disconnected while advancing time"
                ) from exc
            if written == 0:
                raise RuntimeError("BabbleSim PHY request write made no progress")
            packet = packet[written:]

    def _receive_header(self, deadline: float) -> int:
        response = bytearray()
        while len(response) < _HEADER.size:
            self._wait_io(self._read_fd, deadline)
            try:
                chunk = os.read(self._read_fd, _HEADER.size - len(response))
            except BlockingIOError:
                continue
            if not chunk:
                raise RuntimeError("BabbleSim PHY disconnected while advancing time")
            response.extend(chunk)
        return _HEADER.unpack(response)[0]

    def advance_to_us(self, target_us: int) -> int:
        target_us = int(target_us)
        if not 0 <= target_us < (1 << 64) - 1:
            raise ValueError(
                "BabbleSim target must be a finite uint64 time in microseconds"
            )
        if self._write_fd is None:
            raise RuntimeError("BabbleSim clock is not connected")
        if target_us <= self._now_us:
            return self._now_us
        return self._wait_until(target_us)

    def synchronize(self) -> None:
        """Reach the PHY barrier at the current time without advancing it."""
        self._wait_until(self._now_us)

    def _wait_until(self, target_us: int) -> int:
        if self._write_fd is None:
            raise RuntimeError("BabbleSim clock is not connected")
        deadline = time.monotonic() + self.step_timeout
        try:
            self._send(_WAIT.pack(_MSG_WAIT, target_us), deadline)
            header = self._receive_header(deadline)
            if header == _MSG_DISCONNECT:
                raise RuntimeError("BabbleSim PHY disconnected while advancing time")
            if header != _MSG_WAIT_END:
                raise RuntimeError(f"invalid BabbleSim WAIT response: {header:#x}")
        except BaseException:
            self.close()
            raise
        self._now_us = target_us
        return self._now_us

    def close(self) -> None:
        try:
            if self._write_fd is not None:
                try:
                    os.write(self._write_fd, _HEADER.pack(_MSG_DISCONNECT))
                except OSError:
                    pass
        finally:
            self._read_fd = self._write_fd = None
            self._resources.close()
