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

import os
from pathlib import Path

import pytest

from bsworld.devices import ProcessInstance
from bsworld.topology import BluetoothTopology

_PREBUILT_DIR = Path(__file__).parent / "prebuilt"


def _artifact(env_name: str, default_name: str) -> Path:
    return Path(os.environ.get(env_name, _PREBUILT_DIR / default_name)).expanduser().resolve()


def load_qemu_guest(
    topo: BluetoothTopology,
    *,
    controller_address: str,
    label: str,
    log_subdir: Path,
) -> ProcessInstance:
    """Add one QEMU Linux guest and its Virtual Controller to a topology."""
    qemu = _artifact("BSWORLD_QEMU_BIN", "qemu-system-aarch64")
    kernel = _artifact("BSWORLD_QEMU_KERNEL", "Image")
    rootfs = _artifact("BSWORLD_QEMU_ROOTFS", "rootfs.cpio")
    missing = [str(path) for path in (qemu, kernel, rootfs) if not path.is_file()]
    if missing:
        pytest.skip("QEMU Linux artifacts are unavailable: " + ", ".join(missing))

    controller = topo.add_controller(public_address=controller_address)

    def command() -> list[str | Path]:
        if controller.application_dev_id is None:
            raise RuntimeError("QEMU requires a BabbleSim device id")
        return [
            qemu,
            "-M", "virt",
            "-cpu", "cortex-a53",
            "-smp", "1",
            "-m", "256M",
            "-display", "none",
            "-monitor", "none",
            "-nic", "none",
            "-rtc", "base=2026-01-01T00:00:00,clock=vm",
            "-seed", "1",
            "-chardev", "stdio,id=console,signal=off",
            "-serial", "chardev:console",
            "-kernel", kernel,
            "-append", "console=ttyAMA0,115200",
            "-initrd", rootfs,
            "-chardev", f"socket,id=hci,path={controller.hci_sock}",
            "-device", "pci-serial,chardev=hci",
            "-icount",
            (
                f"bsim-sid={controller.sim_id},"
                f"bsim-dev={controller.application_dev_id},"
                f"bsim-phy={controller.phy_id},bsim-mro=1000"
            ),
        ]

    return topo.add_process(
        ProcessInstance(
            command=command,
            controller=controller,
            label=label,
            shell=True,
            log_subdir=log_subdir,
        )
    )


async def login_qemu_guest(guest: ProcessInstance) -> None:
    """Wait for Buildroot login and open a root shell."""
    await guest.wait_log(r"Welcome to Buildroot", timeout=60)
    await guest.shell.run("root")
    await guest.wait_log(r"buildroot login: root", timeout=10)
    await guest.shell.run("echo BSWORLD_LOGIN_READY")
    await guest.wait_log(r"^BSWORLD_LOGIN_READY$", timeout=10)


__all__ = ["load_qemu_guest", "login_qemu_guest"]
