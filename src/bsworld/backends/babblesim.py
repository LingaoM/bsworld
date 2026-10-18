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
"""BabbleSim backend: PHY + virtual HCI controllers + optional interference.

Direct-PHY firmware receives --sim-bsim-* arguments and registers with the
BabbleSim PHY itself.

Bring-up shape:
    1. verify configured BabbleSim and Virtual Controller artifacts.
    2. prepare_sim: kill stragglers for this sim_id, remove stale HCI
       socket files.
    3. assign device ids: Virtual Controllers, Application processes,
       framework clock, then interference.
    4. spawn phy (-D = num_devs).
    5. spawn Virtual Controllers and interference devices. Firmware processes
       are started by topology.
    6. connect the in-process pytest clock after external participants start.
"""
from __future__ import annotations

import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from ..compile import bsim as bsim_build
from ..compile import hci_virt as hci_virt_build
from ..devices.controller import Controller
from ..env import Env
from ..interference import (
    BurstInterference,
    ChannelAttenuation,
    InterferenceSource,
    PlaybackInterference,
    StaticAttenuation,
    TimedAttenuation,
    WlanInterference,
)
from ..log import log, warn
from ..runtime.proc import ProcessManager
from ..runtime.scheduler import BsimClock
from ..runtime.wait import wait_for_path, wait_for_paths

_RESIDUAL_PATTERNS = (
    "bs_2G4_phy_v1",
    "bt_virt_controller",
    "bs_device_2G4_",
)

_PHY_ID = "2G4"
_DEFAULT_MODEM = "BLE_simple"


@dataclass
class BabbleSimBackend:
    env: Env
    sim_id: str
    hci_dump: bool = True
    controllers: list[Controller] = field(default_factory=list)
    channel_attenuation: ChannelAttenuation | None = None
    interference_sources: list[InterferenceSource] = field(default_factory=list)
    _application_controllers: list[Controller] = field(default_factory=list, init=False, repr=False)
    _started: bool = False
    clock: BsimClock | None = None

    def add_controller(self, *, public_address: str | None = None) -> Controller:
        if self._started:
            raise RuntimeError("cannot add a Controller after BabbleSim has started")
        dev_id = len(self.controllers)
        ctl = Controller(
            controller_dev_id=dev_id,
            sim_id=self.sim_id,
            phy_id=_PHY_ID,
            socket_dir=self.env.sim_dir(self.sim_id),
            application_dev_id=None,
            public_address=public_address,
        )
        self.controllers.append(ctl)
        self._assign_application_dev_ids()
        return ctl

    def reserve_application_device(self, controller: Controller) -> None:
        """Reserve a BabbleSim participant for an external Application process."""
        if self._started:
            raise RuntimeError("cannot attach an Application after BabbleSim has started")
        if not any(candidate is controller for candidate in self.controllers):
            raise ValueError("Controller does not belong to this BabbleSim backend")
        if any(candidate is controller for candidate in self._application_controllers):
            return
        self._application_controllers.append(controller)
        self._assign_application_dev_ids()

    def _assign_application_dev_ids(self) -> None:
        application_dev_id = len(self.controllers)
        for index, controller in enumerate(self.controllers):
            controller.controller_dev_id = index
            if any(candidate is controller for candidate in self._application_controllers):
                controller.application_dev_id = application_dev_id
                application_dev_id += 1
            else:
                controller.application_dev_id = None

    def _application_device_count(self) -> int:
        return len(self._application_controllers)

    def check_deps_ready(self) -> None:
        bsim_build.check_ready(self.env)
        hci_virt_build.check_ready(self.env)

    def interference_dev_id(self, index: int) -> int:
        return len(self.controllers) + self._application_device_count() + 1 + index

    def prepare(self) -> None:
        log(f"preparing bsim sim_id={self.sim_id}")
        sim_dir = self.env.sim_dir(self.sim_id)
        sim_dir.mkdir(parents=True, exist_ok=True)
        for pat in _RESIDUAL_PATTERNS:
            subprocess.run(
                ["pkill", "-9", "-f", f"{pat}.*-s={self.sim_id}"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        subprocess.run(
            ["pkill", "-9", "-f", "--", f"--sim-bsim-sid={self.sim_id}"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for ctl in self.controllers:
            for sock in (ctl.hci_sock, ctl.hci_btsnoop_sock):
                if sock.exists():
                    log(f"removing stale {sock}")
                    sock.unlink()

    def start(self, pm: ProcessManager, *, log_dir: Path | None = None, ready_timeout: float = 30.0) -> None:
        log_dir = log_dir or self.env.log_dir
        bsim_log_dir = log_dir / "babblesim"
        if self._started:
            return
        if not self.controllers:
            self._started = True
            return
        self.check_deps_ready()
        self.prepare()

        # dev_id layout:
        #   [0 .. C-1]        bt_virt_controller processes
        #   [C .. C+A-1]      Application processes that join BabbleSim directly
        #   [C+A]             Python test-framework clock device
        #   [C+A+1 ..]        interference devices
        clock_dev_id = len(self.controllers) + self._application_device_count()
        interf_base = self.interference_dev_id(0)
        num_interf = len(self.interference_sources)
        num_devs = interf_base + num_interf

        # Spawn phy.
        phy_bin = self.env.bsim_bin_dir / f"bs_{_PHY_ID}_phy_v1"
        phy_argv: list = [
            phy_bin,
            f"-s={self.sim_id}",
            f"-D={num_devs}",
            f"-defmodem={_DEFAULT_MODEM}",
        ]
        if self.channel_attenuation is not None:
            ca = self.channel_attenuation
            matrix_file = ca.matrix_file
            if ca.static_paths or ca.timed_paths:
                matrix_file = _write_attenuation_matrix(
                    static_paths=ca.static_paths,
                    timed_paths=ca.timed_paths,
                    out_dir=bsim_log_dir,
                )
            phy_argv += ["-channel=multiatt", "-argschannel", f"-at={ca.default_attenuation_db}"]
            if ca.extra_attenuation_db:
                phy_argv.append(f"-atextra={ca.extra_attenuation_db}")
            if matrix_file is not None:
                phy_argv.append(f"-file={matrix_file}")
            # switch back to main phy args so subsequent flags (-dump etc.) are
            # not consumed by the channel plugin
            phy_argv.append("-argsmain")
        if self.env.bsim_ellisys:
            phy_argv.extend(["-dump", "-dump_imm"])
        else:
            phy_argv.append("-nodump")
        phy_process = pm.spawn(
            "bs_2G4_phy_v1",
            phy_argv,
            cwd=self.env.bsim_bin_dir,
            log_dir=bsim_log_dir,
        )
        sim_dir = self.env.sim_dir(self.sim_id)
        wait_for_path(sim_dir / "2G4.phy.lock", timeout=ready_timeout)
        log("phy ready")

        self.clock = BsimClock(
            sim_dir=sim_dir,
            phy_id=_PHY_ID,
            dev_id=clock_dev_id,
            phy_alive=phy_process.alive,
        )

        virt_controller_log_dir = log_dir / "bt_virt_controller"
        controller_bin = hci_virt_build.controller_bin(self.env)
        for ctl in self.controllers:
            controller_argv = [
                controller_bin,
                f"-s={self.sim_id}",
                f"-d={ctl.controller_dev_id}",
                f"-hci-socket={ctl.hci_sock}",
            ]
            if ctl.public_address is not None:
                controller_argv.append(f"-bd-addr={ctl.public_address}")
            if self.hci_dump:
                controller_argv.append(f"-btsnoop-socket={ctl.hci_btsnoop_sock}")
            pm.spawn(
                f"bt_virt_controller_hci{ctl.controller_dev_id}",
                controller_argv,
                cwd=controller_bin.parent,
                log_dir=virt_controller_log_dir,
            )

        for i, src in enumerate(self.interference_sources):
            dev_id = interf_base + i
            argv = _build_interf_argv(src, sim_id=self.sim_id, dev_id=dev_id, bin_dir=self.env.bsim_bin_dir)
            pm.spawn(
                f"interf_{dev_id}",
                argv,
                cwd=self.env.bsim_bin_dir,
                log_dir=bsim_log_dir,
            )
        self._started = True

    def device_lock_paths(self) -> list[Path]:
        if not self.controllers:
            return []
        sim_dir = self.env.sim_dir(self.sim_id)
        device_count = self.interference_dev_id(len(self.interference_sources))
        return [sim_dir / f"{_PHY_ID}.d{dev_id}.lock" for dev_id in range(device_count)]

    def wait_for_devices_registered(self, *, timeout: float = 30.0) -> None:
        locks = self.device_lock_paths()
        if not locks:
            return
        log(f"waiting for {len(locks)} BabbleSim device lock(s)")
        if self.clock is not None:
            self.clock.connect(timeout=timeout)
        wait_for_paths(locks, timeout=timeout)
        log("all devices registered to phy")

    def wait_for_hci_sockets(self, *, timeout: float = 30.0) -> None:
        socks = [ctl.hci_sock for ctl in self.controllers]
        if not socks:
            return
        log(f"waiting for {len(socks)} hci socket(s)")
        wait_for_paths(socks, timeout=timeout)
        log("hci socket(s) bound")

    def wait_for_btsnoop_sockets(self, *, timeout: float = 30.0) -> None:
        if not self.hci_dump:
            return
        socks = [ctl.hci_btsnoop_sock for ctl in self.controllers]
        if not socks:
            return
        log(f"waiting for {len(socks)} HCI BTSnoop socket(s)")
        wait_for_paths(socks, timeout=timeout)
        log("HCI BTSnoop socket(s) bound")

    def finish(self, *, log_dir: Path | None = None) -> None:
        if self.clock is not None:
            try:
                self.clock.close()
            except Exception as exc:
                warn(f"simulation clock close failed: {exc}")
            finally:
                self.clock = None
        if not self.controllers:
            return
        try:
            if self.env.bsim_ellisys:
                self.convert_ellisys(log_dir=log_dir)
        finally:
            self.cleanup_sim_artifacts()

    def convert_ellisys(self, *, log_dir: Path | None = None) -> None:
        if self.env.bsim_dir is None:
            return
        converter = self.env.bsim_ellisys_script or (
            self.env.babblesim_components_dir
            / "ext_2G4_phy_v1"
            / "dump_post_process"
            / "convert_results_to_ellisysv2.sh"
        )
        results_dir = self.env.bsim_dir / "results" / self.sim_id
        tx_files = sorted(results_dir.glob("d_2G4*.Tx.csv"))
        if not converter.is_file():
            warn(f"Ellisys converter not found: {converter}")
            return
        if not tx_files:
            warn(f"no BabbleSim Tx CSV dumps found under {results_dir}")
            return

        out_dir = (log_dir or self.env.log_dir) / "babblesim"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "ellisys.bttrp"
        quoted_inputs = " ".join(shlex.quote(str(path)) for path in tx_files)
        log(
            "converting BabbleSim dump to Ellisys: "
            f"bash {shlex.quote(str(converter))} {quoted_inputs} > {shlex.quote(str(out_path))}"
        )
        with open(out_path, "w") as out:
            rc = subprocess.run(
                ["bash", str(converter), *[str(path) for path in tx_files]],
                cwd=str(converter.parent),
                stdout=out,
            ).returncode
        if rc != 0:
            warn(f"Ellisys conversion failed for {self.sim_id} (exit {rc})")

    def cleanup_sim_artifacts(self) -> None:
        sim_state_dir = self.env.sim_dir(self.sim_id)
        if sim_state_dir.exists():
            log(f"removing sim state {sim_state_dir}")
            shutil.rmtree(sim_state_dir, ignore_errors=True)

        results_dir = self.env.bsim_dir / "results" / self.sim_id if self.env.bsim_dir else None
        if results_dir is not None and results_dir.exists():
            log(f"removing bsim results {results_dir}")
            shutil.rmtree(results_dir, ignore_errors=True)

        for ctl in self.controllers:
            for sock in (ctl.hci_sock, ctl.hci_btsnoop_sock):
                if sock.exists():
                    try:
                        sock.unlink()
                    except FileNotFoundError:
                        pass


def _write_attenuation_matrix(
    *,
    static_paths: list[StaticAttenuation],
    timed_paths: list[TimedAttenuation],
    out_dir: Path,
) -> Path:
    """Write per-path static/timed attenuation files + matrix_file into out_dir.

    Files are placed in the test log directory so they survive cleanup and are
    available for post-mortem inspection alongside bsworld.log and HCI snoops.
    Returns the path to the generated matrix file ready for -file=<path>.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    matrix_lines = [
        f"{path.tx} {path.rx} : {path.attenuation_db}"
        for path in static_paths
    ]
    for i, tp in enumerate(timed_paths):
        timed_file = out_dir / f"timed_att_{tp.tx}_{tp.rx}_{i}.txt"
        with open(timed_file, "w") as fh:
            for t, att in zip(tp.times_us, tp.attenuation_db):
                fh.write(f"{t}    {att}\n")
        matrix_lines.append(f'{tp.tx} {tp.rx} : "{timed_file}"')

    matrix_file = out_dir / "att_matrix.txt"
    with open(matrix_file, "w") as fh:
        fh.write("\n".join(matrix_lines) + "\n")
    return matrix_file


def _build_interf_argv(
    src: InterferenceSource,
    *,
    sim_id: str,
    dev_id: int,
    bin_dir: Path,
) -> list:
    common = [f"-s={sim_id}", f"-d={dev_id}"]

    if isinstance(src, BurstInterference):
        argv: list = [bin_dir / "bs_device_2G4_burst_interf"] + common
        argv += [f"-centerfreq={src.center_freq_mhz}", f"-power={src.power_dbm}", f"-type={src.interf_type}"]
        if src.rand_seed is not None:
            argv.append(f"-rs={src.rand_seed}")
        _append_windows(argv, src.windows)
        return argv

    if isinstance(src, WlanInterference):
        argv = [bin_dir / "bs_device_2G4_WLAN_actmod"] + common
        if src.channel is not None:
            argv.append(f"-channel={src.channel}")
        else:
            argv.append(f"-centerfreq={src.center_freq_mhz}")
        argv += [f"-power={src.power_dbm}", f"-mod={src.mod_type}", f"-ConfigSet={src.config_set}"]
        if src.rand_seed is not None:
            argv.append(f"-rs={src.rand_seed}")
        _append_windows(argv, src.windows)
        return argv

    if isinstance(src, PlaybackInterference):
        argv = [bin_dir / "bs_device_2G4_playbackv2"] + common
        argv.append(f"-inputf={src.input_file}")
        if not src.tx:
            argv.append("-txoff")
        if not src.rx:
            argv.append("-rxoff")
        if not src.rssi:
            argv.append("-rssioff")
        if not src.cca:
            argv.append("-ccaoff")
        return argv

    raise TypeError(f"unknown interference source type: {type(src)}")


def _append_windows(argv: list, windows: list[tuple[int, int]]) -> None:
    if not windows:
        return
    argv.append("-timestart")
    argv.extend(str(start) for start, _ in windows)
    argv.append("-timeend")
    argv.extend(str(end) for _, end in windows)
