# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""H4 framing and the Unix-socket HCI transport (Core Vol 4, Part A).

Covers the byte-level HCI transport plumbing:

- ``H4Parser`` reassembles commands and ACL data from arbitrarily fragmented
  input, emits each complete packet once and rejects an invalid H4 type;
- ``H4Server`` listens on a Unix socket, forwards Host bytes to the endpoint
  and the endpoint's replies back, closes cleanly on Host disconnect, preserves
  a pre-existing socket path, and closes a connected Host on shutdown.

These tests use lightweight endpoint doubles, not a full Controller.
"""

import asyncio
from types import SimpleNamespace

import pytest

from bscontroller.hci.transport import H4Parser, H4Server


def test_h4_parser_retains_fragmented_headers_payloads_and_adjacent_packets():
    """The H4 parser reassembles fragmented and adjacent packets, rejects bad types.

    Purpose: Verify ``H4Parser`` emits exactly one complete packet per H4 frame
    even when fed one byte at a time across a command and an ACL packet, leaves
    no residue, and raises on an unknown H4 packet type.

    Steps:
        1. Feed a Reset command followed by an ACL packet byte by byte.
        2. Inspect the collected packets and the parser buffer.
        3. Feed a single 0xFF byte (invalid H4 type).

    Expected:
        - The two original packets are emitted in order and the buffer is empty.
        - Feeding 0xFF raises ``ValueError`` mentioning 'invalid H4'.
    """
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
    """The Unix server forwards bytes both ways and finishes on Host disconnect.

    Purpose: Verify ``H4Server`` delivers Host command bytes to the endpoint,
    returns the endpoint's reply to the Host, and completes its ``finished``
    future when the Host closes, removing the socket on context exit.

    Steps:
        1. Serve an endpoint that echoes a Command Complete when it receives the
           Reset command.
        2. Connect over the Unix socket, send the command and read 7 reply
           bytes.
        3. Close the client and await the server's ``finished``.

    Expected:
        - The reply equals the Command Complete bytes.
        - ``finished`` resolves after disconnect and the socket path is gone.
    """

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
        assert await asyncio.wait_for(reader.readexactly(7), 1) == bytes.fromhex(
            '040e0401030c00'
        )
        writer.close()
        await writer.wait_closed()
        await asyncio.wait_for(endpoint.finished, 1)
    assert not path.exists()


async def test_existing_socket_path_is_preserved(tmp_path):
    """The server refuses to bind over an existing path and leaves it intact.

    Purpose: Verify ``H4Server`` raises ``FileExistsError`` rather than binding
    when the socket path already exists, and does not overwrite or remove the
    pre-existing file.

    Steps:
        1. Write a file at the intended socket path.
        2. Attempt to enter an ``H4Server`` bound to that path.

    Expected:
        - ``FileExistsError`` is raised.
        - The original file content is unchanged.
    """
    path = tmp_path / 'existing'
    path.write_bytes(b'owned by another process')
    async with asyncio.timeout(1):
        with pytest.raises(FileExistsError):
            async with H4Server(
                SimpleNamespace(set_packet_sink=lambda sink: None), path
            ):
                pass
    assert path.read_bytes() == b'owned by another process'


async def test_server_shutdown_closes_a_connected_host(tmp_path):
    """Server shutdown closes a still-connected Host and removes the socket.

    Purpose: Verify that exiting the ``H4Server`` context while a Host is still
    connected closes the Host connection (the reader sees EOF) and removes the
    socket path.

    Steps:
        1. Serve a controller double that sets an event when it gets a packet.
        2. Connect, send the Reset command and wait for the controller to
           receive it.
        3. Exit the server context.

    Expected:
        - After shutdown the Host reader reads b'' (EOF) and the socket path no
          longer exists.
    """
    received = asyncio.Event()
    controller = SimpleNamespace(
        set_packet_sink=lambda sink: None,
        on_packet=lambda packet: received.set(),
    )
    path = tmp_path / 'hci.sock'
    writer = None
    try:
        async with asyncio.timeout(1):
            async with H4Server(controller, path):
                reader, writer = await asyncio.open_unix_connection(path)
                writer.write(bytes.fromhex('01030c00'))
                await writer.drain()
                await received.wait()
            assert await reader.read(1) == b''
            assert not path.exists()
    finally:
        if writer is not None:
            writer.close()
            await writer.wait_closed()
