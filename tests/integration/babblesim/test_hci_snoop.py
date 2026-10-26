# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Validate Controller-owned BTSnoop files against real HCI traffic and time."""

from __future__ import annotations

import asyncio
import socket
import struct
import uuid

import pytest

from bsworld.backends.babblesim import BabbleSimBackend
from bsworld.devices import BSController, ZephyrController
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


async def test_controller_snoop_preserves_h4_packets_and_controller_timestamps(
    tmp_path,
):
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
        length, included, flags, drops, timestamp = _RECORD.unpack_from(
            before_stop, offset
        )
        offset += _RECORD.size
        assert length == included == len(packet)
        assert flags == index % 2
        assert drops == 0
        assert timestamp - _EPOCH_US == 11000 + (index // 2) * 10000
        assert before_stop[offset : offset + included] == packet
        offset += included
    assert offset == len(before_stop)


@pytest.mark.parametrize(
    "controller_type", [ZephyrController, BSController], ids=["zephyr", "python"]
)
@pytest.mark.parametrize(
    "custom_path", [False, True], ids=["default-path", "application-path"]
)
async def test_snoop_matches_live_h4_traffic_without_host_relay(
    topo, tmp_path, controller_type, custom_path
):
    ctl = topo.add_controller(
        controller_type=controller_type, public_address="F0:F1:F2:F3:F4:01"
    )
    if custom_path:
        ctl.hci_snoop_file = tmp_path / "application" / "hci0.snoop"
    await topo.start()
    reader, writer = await asyncio.open_unix_connection(ctl.hci_sock)
    packets = []
    try:
        async with asyncio.timeout(5):
            for command, response in (
                ("01030c00", "040e0401030c00"),
                ("01091000", "040e0a0109100001f4f3f2f1f0"),
            ):
                packet = bytes.fromhex(command)
                # Fragmented socket writes must produce one captured H4 packet.
                writer.write(packet[:2])
                await writer.drain()
                await asyncio.sleep(0)
                writer.write(packet[2:])
                await writer.drain()
                header = await reader.readexactly(3)
                event = header + await reader.readexactly(header[2])
                assert event == bytes.fromhex(response)
                packets.extend([packet, event])
        before_stop = ctl.hci_snoop_file.read_bytes()
        assert not list(ctl.socket_dir.glob("*.btsnoop.sock"))
    finally:
        writer.close()
        await writer.wait_closed()
        await topo.stop()
    assert ctl.hci_snoop_file.read_bytes() == before_stop
    assert before_stop[:16] == _FILE_HEADER
    offset = 16
    timestamps = []
    for index, packet in enumerate(packets):
        length, included, flags, drops, timestamp = _RECORD.unpack_from(
            before_stop, offset
        )
        offset += _RECORD.size
        assert length == included == len(packet)
        assert flags == index % 2
        assert drops == 0
        assert before_stop[offset : offset + included] == packet
        timestamps.append(timestamp - _EPOCH_US)
        offset += included
    assert offset == len(before_stop)
    assert timestamps == sorted(timestamps)
    # Immediate HCI replies retain the command's local time even though socket
    # delivery happens later in the Host/framework event loop.
    assert timestamps[0] == timestamps[1]
    assert timestamps[2] == timestamps[3]
    assert all(timestamp >= 0 for timestamp in timestamps)
