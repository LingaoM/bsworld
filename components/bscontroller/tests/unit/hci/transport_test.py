# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

import asyncio
from types import SimpleNamespace

import pytest

from bscontroller.hci.transport import H4Parser, H4Server


def test_h4_parser_retains_fragmented_headers_payloads_and_adjacent_packets():
    packets = []
    parser = H4Parser(SimpleNamespace(on_packet=packets.append))
    command = bytes.fromhex('01030c00')
    acl = bytes.fromhex('0201000300616263')
    for byte in command + acl:
        parser.feed_data(bytes([byte]))
    assert packets == [command, acl]
    assert parser.buffer == b''
    with pytest.raises(ValueError, match='invalid H4'):
        parser.feed_data(b'\xff')


async def test_unix_server_forwards_packets_and_closes_on_host_disconnect(tmp_path):
    class Endpoint:
        sink = None

        def set_packet_sink(self, sink):
            self.sink = sink

        def on_packet(self, packet):
            assert packet == bytes.fromhex('01030c00')
            self.sink.on_packet(bytes.fromhex('040e0401030c00'))

    path = tmp_path / 'hci.sock'
    async with H4Server(Endpoint(), path) as endpoint:
        reader, writer = await asyncio.open_unix_connection(path)
        writer.write(bytes.fromhex('01030c00'))
        await writer.drain()
        assert await asyncio.wait_for(reader.readexactly(7), 1) == bytes.fromhex('040e0401030c00')
        writer.close()
        await writer.wait_closed()
        await asyncio.wait_for(endpoint.finished, 1)
    assert not path.exists()


async def test_existing_socket_path_is_preserved(tmp_path):
    path = tmp_path / 'existing'
    path.write_bytes(b'owned by another process')
    async with asyncio.timeout(1):
        with pytest.raises(FileExistsError):
            async with H4Server(SimpleNamespace(set_packet_sink=lambda sink: None), path):
                pass
    assert path.read_bytes() == b'owned by another process'
