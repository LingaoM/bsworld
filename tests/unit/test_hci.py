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

import socket

from bsworld.hci.socket_capture import BtsnoopSocketCapture


async def test_btsnoop_socket_capture_copies_controller_stream_to_file(tmp_path) -> None:
    sock_path = tmp_path / "hci0.btsnoop.sock"
    output_path = tmp_path / "devices" / "dev0" / "hci0.snoop"
    payload = b"btsnoop\x00\x00\x00\x00\x01\x00\x00\x03\xea"
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(sock_path))
    server.listen(1)
    server.settimeout(1.0)
    capture = BtsnoopSocketCapture(socket_path=sock_path, output_path=output_path)
    conn: socket.socket | None = None

    try:
        await capture.start(timeout=1.0)
        conn, _ = server.accept()
        conn.sendall(payload)
        conn.close()
        conn = None

        await capture.stop(timeout=1.0)

        assert output_path.read_bytes() == payload
    finally:
        if conn is not None:
            conn.close()
        await capture.stop(timeout=1.0)
        server.close()
