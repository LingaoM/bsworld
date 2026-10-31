# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Create and register complete upstream Zephyr firmware."""

import os
from pathlib import Path

from bsworld.devices import ProcessInstance
from bsworld.topology import BluetoothTopology


def create_complete_zephyr(
    topo: BluetoothTopology, binary: Path, *, name: str, seed: int, shell: bool = False
) -> ProcessInstance:
    bsim_dir = topo.env.bsim_dir
    library_path = os.pathsep.join(
        filter(
            None,
            [
                str(bsim_dir / "lib") if bsim_dir else "",
                os.environ.get("LD_LIBRARY_PATH", ""),
            ],
        )
    )
    return topo.add_process(
        ProcessInstance(
            command=lambda slot: [
                binary,
                f"-s={slot.sim_id}",
                f"-p={slot.phy_id}",
                f"-d={slot.dev_id}",
                f"-rs={seed}",
                "-mro=1000",
                "-RealEncryption=1",
            ],
            label=name,
            shell=shell,
            # No cwd override: the process runs in its own log directory,
            # which keeps flash and settings files isolated per device.
            log_subdir=Path("zephyr") / "complete" / name,
            # -RealEncryption=1 dlopen()s libCryptov1.so from ../lib or
            # LD_LIBRARY_PATH; the process does not run from BabbleSim's bin/.
            env={"LD_LIBRARY_PATH": library_path},
        )
    )
