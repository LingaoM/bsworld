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

"""Shared helpers for Linux guests running under QEMU."""

from __future__ import annotations

from pathlib import Path

from tests.integration.applications import add_application, require_artifact

from bsworld.devices import AppSlot, ProcessInstance
from bsworld.topology import BluetoothTopology

_GUIDE = "tests/integration/qemu/README.md"


def _artifact(env_name: str, *, executable: bool = False) -> Path:
    return require_artifact(env_name, guide=_GUIDE, executable=executable)


def load_qemu_guest(
    topo: BluetoothTopology,
    *,
    controller_address: str,
    label: str,
    log_subdir: Path,
) -> ProcessInstance:
    """Add one QEMU Linux guest and its Virtual Controller to a topology."""
    # The guest image and kernel are inputs to the emulator rather than the
    # Application executable, so they are resolved before the shared helper.
    kernel = _artifact("BSWORLD_QEMU_KERNEL")
    rootfs = _artifact("BSWORLD_QEMU_ROOTFS")

    def argv(qemu: Path, slot: AppSlot) -> list[str | Path]:
        return [
            qemu,
            "-M",
            "virt",
            "-cpu",
            "cortex-a53",
            "-smp",
            "1",
            "-m",
            "256M",
            "-display",
            "none",
            "-monitor",
            "none",
            "-nic",
            "none",
            "-rtc",
            "base=2026-01-01T00:00:00,clock=vm",
            "-seed",
            "1",
            "-chardev",
            "stdio,id=console,signal=off",
            "-serial",
            "chardev:console",
            "-kernel",
            kernel,
            "-append",
            "console=ttyAMA0,115200",
            "-initrd",
            rootfs,
            "-chardev",
            f"socket,id=hci,path={slot.hci_sock}",
            "-device",
            "pci-serial,chardev=hci",
            "-icount",
            (
                f"bsim-sid={slot.sim_id},"
                f"bsim-dev={slot.dev_id},"
                f"bsim-phy={slot.phy_id},bsim-mro=1000"
            ),
        ]

    return add_application(
        topo,
        binary_env="BSWORLD_QEMU_BIN",
        guide=_GUIDE,
        argv=argv,
        label=label,
        controller_address=controller_address,
        log_subdir=log_subdir,
        shell=True,
    )


async def login_qemu_guest(guest: ProcessInstance) -> None:
    """Wait for Buildroot login and open a root shell."""
    await guest.wait_log(r"Welcome to Buildroot", timeout=60)
    await guest.shell.run("root")
    await guest.wait_log(r"buildroot login: root", timeout=10)
    await guest.shell.run("echo BSWORLD_LOGIN_READY")
    await guest.wait_log(r"^BSWORLD_LOGIN_READY$", timeout=10)


__all__ = ["load_qemu_guest", "login_qemu_guest"]
