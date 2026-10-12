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
"""BluetoothTopology: declarative wiring for one test case.

Lifecycle (driven by the `topo` fixture):
    1. test code registers controllers, processes, and RF conditions. These
       calls only record the topology; nothing has been spawned yet.
    2. test code calls topology.start()
       — BabbleSim backend brings up the PHY/controllers/interference devices,
       then every registered process starts and joins the PHY directly.
    3. pytest joins the PHY through its FIFO clock and binds the event loop.
    4. fixture teardown calls topology.stop() — the process manager stops
       child processes and the backend releases its clock and artifacts.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from bsworld.runtime.scheduler import BsimEventLoop

from .backends.babblesim import BabbleSimBackend
from .devices.controller import Controller, normalize_controller_address
from .devices.instance import ProcessInstance
from .env import Env
from .hci.socket_capture import BtsnoopSocketCapture
from .interference import (
    BurstInterference,
    ChannelAttenuation,
    InterferenceRef,
    InterfType,
    PlaybackInterference,
    StaticAttenuation,
    TimedAttenuation,
    WlanConfigSet,
    WlanInterference,
)
from .log import close_log_file, open_log_file, warn
from .runtime.proc import ProcessManager

_HCI_CONNECT_TIMEOUT_S = 30.0


@dataclass
class BluetoothTopology:
    env: Env
    sim_id: str
    test_log_dir: Path
    hci_dump: bool = True
    pm: ProcessManager = field(default_factory=ProcessManager)
    bsim: BabbleSimBackend = field(init=False)
    processes: list[ProcessInstance] = field(default_factory=list)
    _controller_log_dirs: list[tuple[Controller, Path]] = field(default_factory=list, init=False, repr=False)
    _btsnoop_captures: list[BtsnoopSocketCapture] = field(default_factory=list, init=False, repr=False)
    _event_loop: BsimEventLoop | None = field(default=None, init=False, repr=False)
    _started: bool = False

    def __post_init__(self) -> None:
        self.bsim = BabbleSimBackend(self.env, self.sim_id)
        self.env.out_dir.mkdir(parents=True, exist_ok=True)
        self.test_log_dir.mkdir(parents=True, exist_ok=True)

    # ------------- process registration -------------

    def _ensure_configurable(self) -> None:
        if self._started:
            raise RuntimeError("cannot modify a topology after it has started")

    def add_controller(
        self,
        *,
        public_address: str | None = None,
        log_subdir: Path | str | None = None,
    ) -> Controller:
        """Allocate a Virtual Controller for one Bluetooth Host."""
        self._ensure_configurable()
        if public_address is not None:
            public_address = normalize_controller_address(public_address)
        controller = self.bsim.add_controller(public_address=public_address)
        log_path = (
            Path(log_subdir) if log_subdir is not None else Path("controllers") / f"hci{controller.controller_dev_id}"
        )
        self._controller_log_dirs.append((controller, log_path))
        return controller

    def add_process(self, process: ProcessInstance) -> ProcessInstance:
        """Register an Application process that will be started with the topology."""
        self._ensure_configurable()
        if any(existing.label == process.label for existing in self.processes):
            raise ValueError(f"Application process label is already registered: {process.label}")
        if any(existing.controller is process.controller for existing in self.processes):
            raise ValueError("a Virtual Controller can only be attached to one Application process")
        self.bsim.reserve_application_device(process.controller)
        for index, (controller, _) in enumerate(self._controller_log_dirs):
            if controller is process.controller:
                self._controller_log_dirs[index] = (controller, process.log_subdir)
                break
        else:
            self._controller_log_dirs.append((process.controller, process.log_subdir))
        self.processes.append(process)
        return process

    # ------------- interference -------------

    def set_channel_attenuation(
        self,
        *,
        default_db: float = 60.0,
        extra_db: float = 0.0,
        matrix_file: "Path | None" = None,
        static_paths: "list[StaticAttenuation] | None" = None,
        timed_paths: "list[TimedAttenuation] | None" = None,
    ) -> None:
        """Configure PHY channel attenuation (multiatt model).

        Use static_paths for fixed per-path attenuation and timed_paths for
        dynamic per-path attenuation that varies over simulation time.
        """
        self._ensure_configurable()
        self.bsim.channel_attenuation = ChannelAttenuation(
            default_attenuation_db=default_db,
            extra_attenuation_db=extra_db,
            matrix_file=matrix_file,
            static_paths=static_paths or [],
            timed_paths=timed_paths or [],
        )

    def add_burst_interference(
        self,
        center_freq_mhz: float,
        *,
        power_dbm: float = 20.0,
        interf_type: InterfType = "CW",
        windows: "list[tuple[int, int]] | None" = None,
        rand_seed: "int | None" = None,
    ) -> InterferenceRef:
        """Inject a burst interferer at the given frequency.

        windows: list of (start_us, end_us) pairs; omit for full-simulation interference.
        """
        return self._add_interference_source(
            BurstInterference(
                center_freq_mhz=center_freq_mhz,
                power_dbm=power_dbm,
                interf_type=interf_type,
                windows=windows or [],
                rand_seed=rand_seed,
            )
        )

    def add_wlan_interference(
        self,
        *,
        channel: "int | None" = None,
        center_freq_mhz: "float | None" = None,
        power_dbm: float = 20.0,
        config_set: WlanConfigSet = "5",
        mod_type: InterfType = "WLAN",
        windows: "list[tuple[int, int]] | None" = None,
        rand_seed: "int | None" = None,
    ) -> InterferenceRef:
        """Inject a WLAN activity model interferer.

        Specify either channel (1-14) or center_freq_mhz.
        """
        return self._add_interference_source(
            WlanInterference(
                channel=channel,
                center_freq_mhz=center_freq_mhz,
                power_dbm=power_dbm,
                config_set=config_set,
                mod_type=mod_type,
                windows=windows or [],
                rand_seed=rand_seed,
            )
        )

    def add_playback_interference(self, input_file: "Path | str") -> InterferenceRef:
        """Replay recorded interference from BabbleSim CSV dumps.

        input_file: path prefix without extension (.Tx/.Rx/.RSSI/.CCA.csv expected alongside).
        """
        return self._add_interference_source(PlaybackInterference(input_file=Path(input_file)))

    def _add_interference_source(self, source) -> InterferenceRef:
        self._ensure_configurable()
        ref = InterferenceRef(len(self.bsim.interference_sources))
        self.bsim.interference_sources.append(source)
        return ref

    # ------------- start / stop -------------

    async def start(self) -> None:
        if self._started:
            return
        open_log_file(self.test_log_dir / "bsworld.log")
        self.pm.install_signal_handlers()
        self.bsim.hci_dump = self.hci_dump
        self._resolve_channel_attenuation()
        self.bsim.start(self.pm, log_dir=self.test_log_dir)
        self.bsim.wait_for_hci_sockets()
        await self._setup_hci()
        for process in self.processes:
            process.start(self.pm, self.test_log_dir)
        await asyncio.to_thread(self.bsim.wait_for_devices_registered)
        if self.bsim.clock is not None:
            loop = asyncio.get_running_loop()
            if not isinstance(loop, BsimEventLoop):
                raise RuntimeError("the active asyncio event loop is not BSIM-aware")
            # Registration alone does not mean every device has yielded to PHY.
            self.bsim.clock.synchronize()
            self._event_loop = loop
            self._event_loop.bind_clock(self.bsim.clock)
        self._started = True

    async def _setup_hci(self) -> None:
        if not self.hci_dump:
            return

        self.bsim.wait_for_btsnoop_sockets()
        for ctl, log_subdir in self._controller_log_dirs:
            btsnoop_dir = self.test_log_dir / log_subdir
            capture = BtsnoopSocketCapture(
                socket_path=ctl.hci_btsnoop_sock,
                output_path=btsnoop_dir / f"hci{ctl.controller_dev_id}.snoop",
            )
            await capture.start(timeout=_HCI_CONNECT_TIMEOUT_S)
            self._btsnoop_captures.append(capture)

    def _resolve_channel_attenuation(self) -> None:
        ca = self.bsim.channel_attenuation
        if ca is None:
            return
        if not self.bsim.controllers:
            return
        if ca.matrix_file is not None:
            return

        static_paths = [
            StaticAttenuation(
                tx=self._resolve_path_endpoint(path.tx),
                rx=self._resolve_path_endpoint(path.rx),
                attenuation_db=path.attenuation_db,
            )
            for path in ca.static_paths
        ]
        timed_paths = [
            TimedAttenuation(
                tx=self._resolve_path_endpoint(path.tx),
                rx=self._resolve_path_endpoint(path.rx),
                times_us=path.times_us,
                attenuation_db=path.attenuation_db,
            )
            for path in ca.timed_paths
        ]
        ca.static_paths[:] = static_paths
        ca.timed_paths[:] = timed_paths

    def _resolve_path_endpoint(self, endpoint) -> int:
        if isinstance(endpoint, bool):
            raise TypeError(f"unsupported attenuation endpoint: {endpoint!r}")
        if isinstance(endpoint, int):
            if endpoint < 0:
                raise ValueError("attenuation endpoint device id must be non-negative")
            return endpoint
        if isinstance(endpoint, InterferenceRef):
            if (
                isinstance(endpoint.index, bool)
                or not isinstance(endpoint.index, int)
                or not 0 <= endpoint.index < len(self.bsim.interference_sources)
            ):
                raise ValueError(f"unknown interference source ref: {endpoint.index}")
            if not self.bsim.controllers:
                raise ValueError("cannot resolve interference source without BabbleSim controllers")
            return self.bsim.interference_dev_id(endpoint.index)
        if isinstance(endpoint, ProcessInstance):
            endpoint = endpoint.controller
        if not isinstance(endpoint, Controller):
            raise TypeError(f"unsupported attenuation endpoint: {endpoint!r}")
        if not any(controller is endpoint for controller in self.bsim.controllers):
            raise ValueError("attenuation endpoint Controller does not belong to this topology")
        return endpoint.controller_dev_id

    async def stop(self) -> None:
        clock = self.bsim.clock
        if self._event_loop is not None:
            try:
                self._event_loop.unbind_clock(clock)
            except Exception as exc:
                warn(f"simulation clock unbind failed: {exc}")
            finally:
                self._event_loop = None
        try:
            await asyncio.to_thread(self.pm.cleanup)
        finally:
            self.pm.restore_signal_handlers()
            await self._stop_btsnoop_captures()
            for process in self.processes:
                try:
                    process.stop_capture()
                except Exception as exc:
                    warn(f"{process.label}: failed to stop log capture: {exc}")
            try:
                self.bsim.finish(log_dir=self.test_log_dir)
            finally:
                close_log_file()

    async def _stop_btsnoop_captures(self) -> None:
        for capture in self._btsnoop_captures:
            try:
                await capture.stop()
            except Exception as exc:
                warn(f"BTSnoop socket capture stop failed: {exc}")
        self._btsnoop_captures.clear()
