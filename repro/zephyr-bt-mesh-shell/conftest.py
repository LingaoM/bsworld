# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Run the Zephyr Bluetooth Mesh shell (tests/bluetooth/mesh_shell) on nrf52_bsim.

MESH_SHELL_EXE is the image with every Mesh shell model, including the
Firmware Update models. MESH_SHELL_BLOB_EXE is the same image without the
Firmware Update models, which the BLOB Transfer Client commands require.
"""

import asyncio
import os
import re
from pathlib import Path

import pytest
import pytest_asyncio

from bsworld.devices import ProcessInstance

pytest_plugins = ["bsworld.plugin"]

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\r")
DEFAULT_KEY = "0123456789abcdef0123456789abcdef"
CID = "0x05f1"


def _image(variable: str) -> Path:
    value = os.environ.get(variable)
    if not value:
        pytest.skip(f"{variable} is not set; see README.md")
    image = Path(value)
    if not image.is_file():
        pytest.fail(f"{variable} does not exist: {image}")
    return image


class Shell:
    """One Mesh shell process. Commands return the console output they produce."""

    def __init__(self, topo, *, label: str, seed: int, image: Path) -> None:
        library_path = os.pathsep.join(
            filter(
                None,
                [str(topo.env.bsim_dir / "lib"), os.environ.get("LD_LIBRARY_PATH")],
            )
        )
        self.label = label
        self._log = topo.test_log_dir / label / f"{label}.log"
        self._start = 0
        self._command = ""
        self.dev = topo.add_process(
            ProcessInstance(
                command=lambda slot: [
                    image,
                    f"-s={slot.sim_id}",
                    f"-p={slot.phy_id}",
                    f"-d={slot.dev_id}",
                    f"-rs={seed}",
                    "-mro=1000",
                    "-RealEncryption=1",
                ],
                label=label,
                shell=True,
                env={"LD_LIBRARY_PATH": library_path},
            )
        )

    def _size(self) -> int:
        return self._log.stat().st_size if self._log.exists() else 0

    def _text(self, start: int) -> str:
        return ANSI.sub("", self._log.read_bytes()[start:].decode(errors="replace"))

    def alive(self) -> bool:
        proc = self.dev.shell._proc
        return proc is not None and proc.alive()

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
            if not self.alive():
                pytest.fail(f"{self.label}: crashed after {self._command!r}:\n{text}")
            if loop.time() >= deadline:
                pytest.fail(
                    f"{self.label}: {self._command!r}: "
                    f"no {until!r} within {timeout} s:\n{text}"
                )
            await asyncio.sleep(0.1)

    async def boot(self) -> None:
        await self.dev.wait_log(r"Mesh initialized", timeout=10)
        await self.run("mesh init", until="Mesh shell initialized")

    async def provision_local(self, addr: str = "0x0001") -> None:
        """Self-provision with the default network key, the same on every node."""
        await self.run(f"mesh cdb create {DEFAULT_KEY}", settle=0.5)
        await self.run(f"mesh prov local 0 {addr}", until="Local node provisioned")

    async def bind(self, addr: str, mid: str) -> None:
        """Bind AppKey 0 to a model through the Configuration Client."""
        await self.run(
            f"mesh models cfg model app-bind {addr} 0 {mid}",
            until="AppKey successfully bound",
            timeout=15,
        )


async def provision_adv(prov: Shell, node: Shell, uuid: str, addr: str) -> None:
    """Provision node over PB-ADV from prov and make prov target it."""
    await node.run(f"mesh prov uuid {uuid}", until="Device UUID set")
    await node.run("mesh prov pb-adv on", until="PB-ADV enabled")
    await prov.run("mesh prov beacon-listen on", settle=0.2)
    await prov.wait(f"PB-ADV UUID {uuid}", timeout=10)
    await prov.run(
        f"mesh prov remote-adv {uuid} 0 {addr} 5",
        until=f"Node provisioned.*{addr}",
        timeout=30,
    )
    await node.wait(f"Local node provisioned.*{addr}", timeout=10)
    await prov.run("mesh prov beacon-listen off", settle=0.2)
    await prov.run(f"mesh target dst {addr}", until="Destination address set")
    await prov.run("mesh models cfg appkey add 0 0", until="AppKey added", timeout=15)


async def _start(topo, shells: list[Shell]) -> None:
    topo.set_channel_attenuation(default_db=45)
    await topo.start()
    for shell in shells:
        await shell.boot()


@pytest_asyncio.fixture
async def single(topo) -> Shell:
    dut = Shell(topo, label="dut", seed=41, image=_image("MESH_SHELL_EXE"))
    await _start(topo, [dut])
    return dut


@pytest_asyncio.fixture
async def node(single) -> Shell:
    """A self-provisioned node at 0x0001 with AppKey 0 that targets itself."""
    await single.provision_local()
    await single.run("mesh models cfg appkey add 0 0", until="AppKey added", timeout=10)
    return single


@pytest_asyncio.fixture
async def blob_single(topo) -> Shell:
    dut = Shell(topo, label="dut", seed=41, image=_image("MESH_SHELL_BLOB_EXE"))
    await _start(topo, [dut])
    return dut


async def _network(topo, variable: str, count: int) -> list[Shell]:
    image = _image(variable)
    labels = ["prov", "node1", "node2"][:count]
    shells = [
        Shell(topo, label=label, seed=41 + i, image=image)
        for i, label in enumerate(labels)
    ]
    await _start(topo, shells)
    prov = shells[0]
    await prov.provision_local()
    await prov.run("mesh models cfg appkey add 0 0", until="AppKey added", timeout=10)
    return shells


@pytest_asyncio.fixture
async def network(topo) -> list[Shell]:
    """A provisioner at 0x0001 and two unprovisioned nodes."""
    return await _network(topo, "MESH_SHELL_EXE", 3)


@pytest_asyncio.fixture
async def blob_network(topo) -> list[Shell]:
    """The same network with the image without the Firmware Update models."""
    return await _network(topo, "MESH_SHELL_BLOB_EXE", 2)
