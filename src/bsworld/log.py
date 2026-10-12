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
#
"""Coloured stdout logging + Die exception."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import IO, NoReturn


def _now() -> str:
    return f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}]"
_file_sink: IO[str] | None = None


def open_log_file(path: Path) -> None:
    global _file_sink
    close_log_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    _file_sink = path.open("w", buffering=1)


def close_log_file() -> None:
    global _file_sink
    fh = _file_sink
    _file_sink = None
    if fh is not None:
        fh.close()


def _tee(line: str) -> None:
    if _file_sink is not None:
        _file_sink.write(line)
        _file_sink.flush()


def _wrap(code: str, msg: str) -> str:
    return f"\033[{code}m{msg}\033[0m" if sys.stderr.isatty() else msg


def log(msg: str) -> None:
    line = f"{_now()} [bsworld] {msg}\n"
    print(line, end="", flush=True)
    _tee(line)


def info(tag: str, msg: str) -> None:
    line = f"{_now()} [{tag}] {msg}\n"
    print(line, end="", flush=True)
    _tee(line)


def warn(msg: str) -> None:
    line = f"{_now()} [bsworld][WARN] {msg}\n"
    print(_wrap("33", line), end="", file=sys.stderr, flush=True)
    _tee(line)


def err(msg: str) -> None:
    line = f"{_now()} [bsworld][ERROR] {msg}\n"
    print(_wrap("31", line), end="", file=sys.stderr, flush=True)
    _tee(line)


class Die(SystemExit):
    def __init__(self, msg: str, code: int = 1) -> None:
        err(msg)
        super().__init__(code)


def die(msg: str, code: int = 1) -> NoReturn:
    raise Die(msg, code)
