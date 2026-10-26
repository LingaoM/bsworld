# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Run upstream Zephyr Bluetooth and Mesh shells with independent stdin pipes."""

from __future__ import annotations

from pathlib import Path

from tests.integration.applications import add_application

from bsworld.devices import AppSlot, Controller, ProcessInstance
from bsworld.topology import BluetoothTopology


def _argv(binary: Path, slot: AppSlot) -> list[str | Path]:
    return [
        binary,
        f"-s={slot.sim_id}",
        f"-p={slot.phy_id}",
        f"-d={slot.dev_id}",
        "-mro=1000",
        f"--bt-dev={slot.hci_sock}",
    ]


def add_zephyr_shell(
    topo: BluetoothTopology,
    *,
    name: str,
    address: str,
    mesh: bool = False,
    controller_type: type[Controller] | None = None,
) -> ProcessInstance:
    return add_application(
        topo,
        binary_env=(
            "BSWORLD_ZEPHYR_MESH_SHELL_BIN" if mesh else "BSWORLD_ZEPHYR_SHELL_BIN"
        ),
        guide="tests/integration/zephyr/shell/README.md",
        argv=_argv,
        label=name,
        controller_address=address,
        controller_type=controller_type,
        log_subdir=Path("zephyr") / "shell" / name,
        shell=True,
    )


async def initialize_shell(device: ProcessInstance, *, mesh: bool = False) -> None:
    """Finish startup before a scenario selects Bluetooth or Mesh roles."""
    if mesh:
        # The upstream Mesh entry point enables Bluetooth and registers its
        # composition at boot. The command initializes the shell submodules.
        await device.wait_log(r"Mesh initialized", timeout=30.0)
        await device.shell.run("mesh init")
        await device.wait_log(r"Mesh shell initialized", timeout=30.0)
    else:
        # The generic shell leaves Host initialization to the user. Waiting
        # for its startup line avoids using a prompt without a trailing LF.
        await device.wait_log(r"Before any Bluetooth commands", timeout=30.0)
        await device.shell.run("bt init sync")
        await device.wait_log(r"Bluetooth initialized", timeout=30.0)
