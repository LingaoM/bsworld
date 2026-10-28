# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Run the qualification procedures against an external Zephyr Controller.

The IUT is a Zephyr ``nrf52_bsim`` HCI Controller executable (H4 over a Unix
socket, served by the executable) joining the same BabbleSim PHY as device 0.
It replaces the in-process BSController worker behind the same interface, so
the procedures stay pure HCI and air black-box tests.
"""

import asyncio
import os
import socket
import struct
from pathlib import Path

H4_COMMAND = 0x01
H4_ACL = 0x02
H4_SYNC = 0x03
H4_EVENT = 0x04
H4_ISO = 0x05
# Header length and the (offset, struct format) of its length field per type.
H4_HEADERS = {
    H4_ACL: (4, 2, '<H'),
    H4_SYNC: (3, 2, '<B'),
    H4_EVENT: (2, 1, '<B'),
    H4_ISO: (4, 2, '<H'),
}
ISO_LENGTH_MASK = 0x3FFF
# Wall-clock bounds for process start and stop.
START_TIMEOUT_SECONDS = 5.0
STOP_TIMEOUT_SECONDS = 5.0

ZEPHYR_CONTROLLER_ENV = 'QUALIFICATION_ZEPHYR_CONTROLLER'


def zephyr_controller() -> Path | None:
    """The selected Zephyr Controller executable, or None for BSController."""
    value = os.environ.get(ZEPHYR_CONTROLLER_ENV)
    return Path(value) if value else None


class ZephyrController:
    """Duck-typed replacement for RadioControllerWorker (set_packet_sink,
    on_packet, start, close).

    Zephyr polls its socket at 1 ms simulated-time boundaries and writes events
    before requesting its next PHY wait, so after every PHY barrier of the
    lower tester the socket already holds all events up to that time. The
    tester drains them synchronously with ``flush()`` at that point.
    """

    def __init__(self, binary, tmp_path, *, public_address, bsim_bin):
        self.binary = Path(binary)
        self.tmp_path = Path(tmp_path)
        self.public_address = public_address
        self.bsim_bin = Path(bsim_bin)
        self.socket_path = None
        self.sink = None
        self.process = None
        self.socket = None
        self.buffer = bytearray()

    def set_packet_sink(self, sink):
        self.sink = sink

    def on_packet(self, packet):
        self.socket.sendall(bytes(packet))

    async def start(self, sim_id, dev_id):
        # Unix socket paths are limited to 108 bytes; test directories are not.
        self.socket_path = Path('/tmp') / f'{sim_id}_hci{dev_id}.sock'
        self.log = (self.tmp_path / 'controller.log').open('wb')
        # The HW models load ../lib/libCryptov1.so relative to the working dir.
        self.process = await asyncio.create_subprocess_exec(
            self.binary,
            f'-s={sim_id}',
            f'-d={dev_id}',
            '-RealEncryption=1',
            f'-hci-socket={self.socket_path}',
            f'-bd-addr={self.public_address}',
            f'-btsnoop-file={self.tmp_path / "hci.snoop"}',
            cwd=self.bsim_bin,
            stdout=self.log,
            stderr=asyncio.subprocess.STDOUT,
        )
        loop = asyncio.get_running_loop()
        deadline = loop.time() + START_TIMEOUT_SECONDS
        while True:
            try:
                connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                connection.connect(str(self.socket_path))
                break
            except (FileNotFoundError, ConnectionRefusedError):
                connection.close()
                if self.process.returncode is not None or loop.time() > deadline:
                    raise RuntimeError(
                        f'Zephyr Controller socket unavailable: {self.socket_path}'
                    ) from None
                await asyncio.sleep(0.01)
        connection.setblocking(False)
        self.socket = connection

    def flush(self):
        """Deliver every complete H4 packet already written by the Controller."""
        if self.socket is None:
            return
        while True:
            try:
                data = self.socket.recv(65536)
            except BlockingIOError:
                break
            if not data:
                break
            self.buffer += data
        while self.buffer:
            kind = self.buffer[0]
            if kind not in H4_HEADERS:
                raise AssertionError(f'unexpected H4 packet type 0x{kind:02x}')
            header, offset, form = H4_HEADERS[kind]
            if len(self.buffer) < 1 + header:
                return
            (length,) = struct.unpack_from(form, self.buffer, 1 + offset)
            if kind == H4_ISO:
                length &= ISO_LENGTH_MASK
            size = 1 + header + length
            if len(self.buffer) < size:
                return
            packet = bytes(self.buffer[:size])
            del self.buffer[:size]
            if self.sink is not None:
                self.sink.on_packet(packet)

    async def close(self):
        if self.socket is not None:
            self.socket.close()
            self.socket = None
        if self.socket_path is not None:
            self.socket_path.unlink(missing_ok=True)
        if self.process is not None and self.process.returncode is None:
            # SIGTERM lets the simulator detach from the PHY cleanly.
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), STOP_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
        if getattr(self, 'log', None) is not None:
            self.log.close()
