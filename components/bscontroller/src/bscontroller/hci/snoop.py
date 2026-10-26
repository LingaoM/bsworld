# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Controller-owned BTSnoop v1 capture with H4 packets and simulation time."""

from __future__ import annotations

import struct
from collections.abc import Callable
from pathlib import Path

_FILE_HEADER = struct.pack('>8sII', b'btsnoop\0', 1, 1002)
_RECORD_HEADER = struct.Struct('>IIIIQ')
_EPOCH_DELTA_US = 0x00DCDDB30F2F8000


class BtsnoopWriter:
    """Write complete records immediately, from the Controller's owner thread.

    Direction flags match bt_virt_controller: 0 for Host to Controller, 1 for
    Controller to Host. The supplied clock returns local simulation microseconds.
    """

    def __init__(self, path: Path, clock: Callable[[], int]):
        self.clock = clock
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._file = path.open('wb', buffering=0)
        try:
            self._write_all(_FILE_HEADER)
        except BaseException:
            self._file.close()
            raise

    def _write_all(self, data: bytes) -> None:
        remaining = memoryview(data)
        while remaining:
            written = self._file.write(remaining)
            if not written:
                raise OSError('BTSnoop file write made no progress')
            remaining = remaining[written:]

    def capture(self, packet: bytes, *, received: bool) -> None:
        header = _RECORD_HEADER.pack(len(packet), len(packet), int(received), 0, self.clock() + _EPOCH_DELTA_US)
        self._write_all(header + packet)

    def __enter__(self) -> BtsnoopWriter:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self._file.close()
