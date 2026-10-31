# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Create complete and Host-only Zephyr Bluetooth shell descriptions."""

from pathlib import Path

from tests.integration.applications import create_application, require_artifact
from tests.integration.zephyr.devices import create_complete_zephyr

from bsworld.devices import AppSlot, ProcessInstance
from bsworld.topology import BluetoothTopology


def create_zephyr_firmware_shell(
    topo: BluetoothTopology, *, name: str, seed: int = 1
) -> ProcessInstance:
    """Describe a complete upstream image with its own Controller and radio."""
    binary = require_artifact(
        "BSWORLD_ZEPHYR_FULL_SHELL_BIN",
        guide="tests/integration/zephyr/shell/README.md",
    )
    return create_complete_zephyr(topo, binary, name=name, seed=seed, shell=True)


def _argv(binary: Path, slot: AppSlot) -> list[str | Path]:
    return [
        binary,
        f"-s={slot.sim_id}",
        f"-p={slot.phy_id}",
        f"-d={slot.dev_id}",
        "-mro=1000",
        f"--bt-dev={slot.hci_sock}",
    ]


def create_zephyr_shell(topo: BluetoothTopology, *, name: str) -> ProcessInstance:
    """Describe a Host-only shell without selecting its Controller."""
    return create_application(
        topo,
        binary_env="BSWORLD_ZEPHYR_SHELL_BIN",
        guide="tests/integration/zephyr/shell/README.md",
        argv=_argv,
        label=name,
        log_subdir=Path("zephyr") / "shell" / name,
        shell=True,
    )
