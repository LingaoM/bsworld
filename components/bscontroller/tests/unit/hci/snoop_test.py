# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""BTSnoop wire format and capture at Controller-local HCI boundaries."""

import asyncio
import struct
from types import SimpleNamespace

import pytest

from bscontroller.hci.backend import RadioBackend
from bscontroller.hci.controller import Controller
from bscontroller.hci.snoop import BtsnoopWriter

HEADER = bytes.fromhex('6274736e6f6f700000000001000003ea')
EPOCH = 0x00DCDDB30F2F8000


def test_empty_capture_and_completed_records_are_visible_before_close(tmp_path):
    path = tmp_path / 'nested' / 'hci0.snoop'
    now_us = 11000
    with BtsnoopWriter(path, lambda: now_us) as snoop:
        assert path.read_bytes() == HEADER
        command = bytes.fromhex('01030c00')
        snoop.capture(command, received=False)
        # Matches bt_virt_controller's big-endian record, including H4 type.
        expected = HEADER + bytes.fromhex(
            '00000004 00000004 00000000 00000000 00dcddb30f2faaf8 01030c00'
        )
        assert path.read_bytes() == expected
        now_us = 12345
        event = bytes.fromhex('040e0401030c00')
        snoop.capture(event, received=True)
        expected += struct.pack('>IIIIQ', 7, 7, 1, 0, EPOCH + now_us) + event
        assert path.read_bytes() == expected
    assert path.read_bytes() == expected


@pytest.mark.parametrize('received', [False, True])
@pytest.mark.parametrize(
    'packet',
    [
        bytes.fromhex('0201000300616263'),  # ACL
        bytes.fromhex('03010003616263'),  # SCO
        bytes.fromhex('0501000300616263'),  # ISO
        b'\x02\x01\x00\x00\x10' + bytes(4096),
    ],
)
def test_capture_preserves_complete_h4_packets(tmp_path, received, packet):
    path = tmp_path / 'hci.snoop'
    with BtsnoopWriter(path, lambda: 9876543210) as snoop:
        snoop.capture(packet, received=received)
        assert path.read_bytes() == (
            HEADER
            + struct.pack(
                '>IIIIQ', len(packet), len(packet), int(received), 0, EPOCH + 9876543210
            )
            + packet
        )


def test_partial_file_writes_are_completed_and_write_failures_propagate(
    tmp_path, monkeypatch
):
    with BtsnoopWriter(tmp_path / 'hci.snoop', lambda: 0) as snoop:
        original = snoop._file.write
        monkeypatch.setattr(snoop._file, 'write', lambda data: original(data[:3]))
        packet = bytes.fromhex('01030c00')
        snoop.capture(packet, received=False)
        assert (tmp_path / 'hci.snoop').read_bytes() == HEADER + struct.pack(
            '>IIIIQ', 4, 4, 0, 0, EPOCH
        ) + packet
        monkeypatch.setattr(snoop._file, 'write', lambda data: 0)
        with pytest.raises(OSError, match='no progress'):
            snoop.capture(packet, received=False)
    assert snoop._file.closed


@pytest.mark.asyncio
async def test_capture_precedes_host_loop_delivery_and_does_not_advance_time(tmp_path):
    radio = SimpleNamespace(now_us=123)
    delivered = []
    path = tmp_path / 'hci.snoop'
    with BtsnoopWriter(path, lambda: radio.now_us) as snoop:
        controller = Controller(
            'test',
            backend=RadioBackend(radio),
            host_sink=SimpleNamespace(on_packet=delivered.append),
            snoop=snoop,
        )
        controller.on_packet(bytes.fromhex('01030c00'))
        assert radio.now_us == 123
        assert not delivered
        expected = (
            HEADER
            + struct.pack('>IIIIQ', 4, 4, 0, 0, EPOCH + 123)
            + bytes.fromhex('01030c00')
            + struct.pack('>IIIIQ', 7, 7, 1, 0, EPOCH + 123)
            + bytes.fromhex('040e0401030c00')
        )
        assert path.read_bytes() == expected
        radio.now_us = 10000
        await asyncio.sleep(0)
        assert delivered == [bytes.fromhex('040e0401030c00')]
        assert path.read_bytes() == expected
