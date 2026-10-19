# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Validate Controller-owned BTSnoop files against real HCI traffic and time."""

from __future__ import annotations

import socket
import struct
import uuid

from bsworld.backends.babblesim import BabbleSimBackend
from bsworld.env import Env
from bsworld.runtime.proc import ProcessManager

_FILE_HEADER = bytes.fromhex("6274736e6f6f700000000001000003ea")
_RECORD = struct.Struct(">IIIIQ")
_EPOCH_US = 0x00DCDDB30F2F8000


def _receive(sock: socket.socket, length: int) -> bytes:
    data = bytearray()
    while len(data) < length:
        chunk = sock.recv(length - len(data))
        assert chunk, "Controller disconnected before completing HCI response"
        data.extend(chunk)
    return bytes(data)


async def test_controller_snoop_preserves_h4_packets_and_controller_timestamps(tmp_path):
    env = Env.detect()
    backend = BabbleSimBackend(env, f"hci_snoop_{uuid.uuid4().hex[:12]}")
    ctl = backend.add_controller(public_address="F0:F1:F2:F3:F4:01")
    ctl.hci_snoop_file = tmp_path / "host" / "hci0.snoop"
    pm = ProcessManager()
    host = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    host.settimeout(5)
    packets = []
    try:
        await backend.start(pm, log_dir=tmp_path)
        await backend.wait_for_hci_sockets()
        assert ctl.socket_dir.is_dir()
        assert not list(ctl.socket_dir.glob("*.btsnoop.sock"))
        host.connect(str(ctl.hci_sock))
        backend.wait_for_devices_registered()
        clock = backend.clock
        clock.synchronize()
        clock.advance_to_us(10000)
        for command in ("01030c00", "01011000", "01091000", "01022000"):
            packet = bytes.fromhex(command)
            host.sendall(packet)
            clock.advance_to_us(clock.now_us + 10000)
            header = _receive(host, 3)
            assert header[:2] == b"\x04\x0e"
            event = header + _receive(host, header[2])
            assert event[4:6] == packet[1:3]
            packets.extend([packet, event])
        # No Python capture reader or relay is running. Every record must be
        # present on disk before the Controller exits, and survive SIGKILL.
        before_stop = ctl.hci_snoop_file.read_bytes()
    finally:
        host.close()
        pm.cleanup()
        backend.finish(log_dir=tmp_path)
    assert ctl.hci_snoop_file.read_bytes() == before_stop
    assert before_stop[:16] == _FILE_HEADER
    offset = 16
    for index, packet in enumerate(packets):
        length, included, flags, drops, timestamp = _RECORD.unpack_from(before_stop, offset)
        offset += _RECORD.size
        assert length == included == len(packet)
        assert flags == index % 2
        assert drops == 0
        assert timestamp - _EPOCH_US == 11000 + (index // 2) * 10000
        assert before_stop[offset:offset + included] == packet
        offset += included
    assert offset == len(before_stop)
