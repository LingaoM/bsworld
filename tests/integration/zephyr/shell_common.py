# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Startup commands shared by Zephyr Bluetooth shells."""

import re

from bsworld.devices import ProcessInstance


async def initialize_shell(device: ProcessInstance) -> None:
    """Initialize the Bluetooth Host after the shell's startup banner."""
    await device.wait_log(r"Before any Bluetooth commands", timeout=30.0)
    await device.shell.run("bt init sync")
    await device.wait_log(r"Bluetooth initialized", timeout=30.0)


async def shell_identity(device: ProcessInstance) -> str:
    await device.shell.run("bt id-show")
    line = await device.wait_log(r"\*0: [PR]:[0-9A-F:]+")
    return re.search(r"\*0: ([PR]:[0-9A-F:]+)", line)[1]
