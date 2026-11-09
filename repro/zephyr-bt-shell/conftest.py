# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Run the Zephyr Bluetooth shell (tests/bluetooth/shell) on nrf52_bsim.

ZEPHYR_BT_SHELL_EXE is the complete image: Host, Zephyr Controller and
radio. ZEPHYR_BT_SHELL_HOST_EXE is the Host-only image, which connects to a
BSWorld Controller over an HCI socket so that its HCI traffic is captured.
"""

import asyncio
import os
import re
import struct
from pathlib import Path

import pytest
import pytest_asyncio

from bsworld.devices import ProcessInstance

pytest_plugins = ["bsworld.plugin"]

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\r")
ADDRESS = r"[PR]:[0-9A-F]{2}(?::[0-9A-F]{2}){5}"


def _image(variable: str) -> Path:
    value = os.environ.get(variable)
    if not value:
        pytest.skip(f"{variable} is not set; see README.md")
    image = Path(value)
    if not image.is_file():
        pytest.fail(f"{variable} does not exist: {image}")
    return image


class Shell:
    """One shell process. Commands return the console output they produce."""

    def __init__(self, topo, *, label: str, seed: int, host_only: bool = False) -> None:
        library_path = os.pathsep.join(
            filter(
                None,
                [str(topo.env.bsim_dir / "lib"), os.environ.get("LD_LIBRARY_PATH")],
            )
        )
        image = _image(
            "ZEPHYR_BT_SHELL_HOST_EXE" if host_only else "ZEPHYR_BT_SHELL_EXE"
        )
        self.label = label
        self._log = topo.test_log_dir / label / f"{label}.log"
        self._start = 0
        self._command = ""

        def command(slot):
            argv = [
                image,
                f"-s={slot.sim_id}",
                f"-p={slot.phy_id}",
                f"-d={slot.dev_id}",
            ]
            if host_only:
                return [*argv, "-mro=1000", f"--bt-dev={slot.hci_sock}"]
            return [*argv, f"-rs={seed}", "-mro=1000", "-RealEncryption=1"]

        self.dev = topo.add_process(
            ProcessInstance(
                command=command,
                label=label,
                shell=True,
                env={"LD_LIBRARY_PATH": library_path},
                requires_controller=host_only,
            )
        )
        self.controller = None
        if host_only:
            self.controller = topo.add_controller(
                public_address=f"C0:FF:EE:00:00:{seed:02X}"
            )
            self.dev.attach(self.controller)

    def _size(self) -> int:
        return self._log.stat().st_size if self._log.exists() else 0

    def _text(self, start: int) -> str:
        return ANSI.sub("", self._log.read_bytes()[start:].decode(errors="replace"))

    async def run(
        self,
        command: str,
        *,
        until: str | None = None,
        timeout: float = 5.0,
        settle: float = 0.5,
    ) -> str:
        """Send a command and return its output.

        With until, wait up to timeout seconds of simulated time for output
        that matches it and fail with the output if none does. Otherwise
        collect the output of the next settle seconds.
        """
        self._start = self._size()
        self._command = command
        await self.dev.shell.run(command)
        if until is None:
            await asyncio.sleep(settle)
            return self._text(self._start)
        return await self.wait(until, timeout=timeout)

    async def wait(self, until: str, *, timeout: float = 5.0) -> str:
        """Wait for output that matches until since the last command."""
        pattern = re.compile(until)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while True:
            text = self._text(self._start)
            if pattern.search(text):
                return text
            if loop.time() >= deadline:
                pytest.fail(
                    f"{self.label}: {self._command!r}: "
                    f"no {until!r} within {timeout} s:\n{text}"
                )
            await asyncio.sleep(0.1)

    async def boot(self) -> None:
        await self.dev.wait_log(r"Before any Bluetooth commands|uart:~\$", timeout=10)
        await self.run("bt init sync", until="Bluetooth initialized")

    async def identity(self) -> str:
        out = await self.run("bt id-show", until=rf"\*0: {ADDRESS}")
        return re.search(rf"\*0: ({ADDRESS})", out)[1]

    def hci_commands(self, opcode: int) -> list[bytes]:
        """Return the parameters of each captured HCI command with opcode."""
        data = self.controller.hci_snoop_file.read_bytes()
        record = struct.Struct(">IIIIQ")
        offset = 16  # BTSnoop file header, H:4 datalink
        found = []
        while offset + record.size <= len(data):
            _, length, flags, _, _ = record.unpack_from(data, offset)
            offset += record.size
            packet = data[offset : offset + length]
            offset += length
            # flags 2: command or event sent by the Host; H:4 type 1: command
            if flags == 2 and packet[:1] == b"\x01":
                if int.from_bytes(packet[1:3], "little") == opcode:
                    found.append(packet[4 : 4 + packet[3]])
        return found


async def connect(periph: Shell, central: Shell) -> str:
    """Connect central to periph and return the address of periph."""
    address = await periph.identity()
    await periph.run("bt advertise on identity", until="Advertising started")
    await central.run(f"bt connect {address}", until=f"Connected: {re.escape(address)}")
    return address


async def _start(topo, shells: list[Shell]) -> None:
    topo.set_channel_attenuation(default_db=45)
    await topo.start()
    for shell in shells:
        await shell.boot()


@pytest_asyncio.fixture
async def single(topo) -> Shell:
    dut = Shell(topo, label="dut", seed=41)
    await _start(topo, [dut])
    return dut


@pytest_asyncio.fixture
async def host_only(topo) -> Shell:
    dut = Shell(topo, label="host", seed=41, host_only=True)
    await _start(topo, [dut])
    return dut


@pytest_asyncio.fixture
async def pair(topo) -> tuple[Shell, Shell]:
    periph = Shell(topo, label="periph", seed=41)
    central = Shell(topo, label="central", seed=42)
    await _start(topo, [periph, central])
    return periph, central


@pytest_asyncio.fixture
async def trio(topo) -> tuple[Shell, Shell, Shell]:
    listed = Shell(topo, label="listed", seed=41)
    other = Shell(topo, label="other", seed=43)
    central = Shell(topo, label="central", seed=42)
    await _start(topo, [listed, other, central])
    return listed, other, central
