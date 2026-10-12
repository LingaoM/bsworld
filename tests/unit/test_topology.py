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
from __future__ import annotations

import asyncio
import io
import subprocess
from pathlib import Path

import pytest

from bsworld.devices.instance import ProcessInstance
from bsworld.env import Env
from bsworld.interference import (
    InterferenceRef,
    StaticAttenuation,
    TimedAttenuation,
    WlanInterference,
)
from bsworld.runtime.scheduler import BsimEventLoop
from bsworld.topology import BluetoothTopology


def _env(tmp_path: Path) -> Env:
    build = tmp_path / "build"
    bsim_dir = build / "babblesim" / "bsim"
    return Env(
        out_tag="run-test",
        run_uid="uid",
        out_dir=tmp_path / "out",
        log_dir=tmp_path / "out" / "log",
        babblesim_root=tmp_path / "components" / "babblesim",
        hci_virt_bin=tmp_path / "components" / "hci",
        bsim_dir=bsim_dir,
        bsim_bin_dir=bsim_dir / "bin",
        bs_state_dir=tmp_path / "state",
    )


def _register_process(
    topo: BluetoothTopology,
    *,
    exe: str | Path,
    label: str = "device",
    args: tuple[str, ...] = (),
    shell: bool = False,
    log_subdir: Path | str | None = None,
    public_address: str | None = None,
) -> ProcessInstance:
    binary = Path(exe).absolute()
    controller = topo.add_controller(public_address=public_address)
    process = ProcessInstance(
        command=[binary, *args],
        controller=controller,
        label=label,
        shell=shell,
        log_subdir=log_subdir,
    )
    return topo.add_process(process)


def test_add_process_registers_controller_application_device(tmp_path) -> None:
    exe = tmp_path / "firmware"
    exe.write_text("")
    topo = BluetoothTopology(_env(tmp_path), "sim0", tmp_path / "log")

    dev = _register_process(topo, exe=exe, label="dev0", args=("--foo=bar",))

    assert dev.label == "dev0"
    assert dev.controller is topo.bsim.controllers[0]
    assert dev.controller.application_dev_id == 1
    assert dev.controller.hci_sock == tmp_path / "state" / "sim0" / "hci0.sock"


def test_add_controller_allocates_in_process_virtual_controller(tmp_path) -> None:
    topo = BluetoothTopology(_env(tmp_path), "sim0", tmp_path / "log")

    ctl = topo.add_controller(public_address="c0:ff:ee:00:00:03")

    assert ctl is topo.bsim.controllers[0]
    assert ctl.public_address == "C0:FF:EE:00:00:03"
    assert ctl.application_dev_id is None
    assert ctl.hci_sock == tmp_path / "state" / "sim0" / "hci0.sock"


@pytest.mark.parametrize(
    "address",
    [
        "C0:FF:EE:00:00",
        "C0:FF:EE:00:00:01:02",
        "C0:FF:EE:00:00:GG",
        "00:00:00:00:00:00",
    ],
)
def test_add_controller_rejects_invalid_public_address(tmp_path, address: str) -> None:
    topo = BluetoothTopology(_env(tmp_path), "sim0", tmp_path / "log")

    with pytest.raises(ValueError, match="controller address"):
        topo.add_controller(public_address=address)


def test_add_process_rejects_duplicate_label(tmp_path) -> None:
    exe = tmp_path / "firmware"
    exe.write_text("")
    topo = BluetoothTopology(_env(tmp_path), "sim0", tmp_path / "log")
    _register_process(topo, exe=exe, label="device")

    with pytest.raises(ValueError, match="label is already registered"):
        _register_process(topo, exe=exe, label="device")


def test_add_process_rejects_shared_controller(tmp_path) -> None:
    exe = tmp_path / "firmware"
    exe.write_text("")
    topo = BluetoothTopology(_env(tmp_path), "sim0", tmp_path / "log")
    first = _register_process(topo, exe=exe, label="first")
    second = ProcessInstance(command=[exe], controller=first.controller, label="second")

    with pytest.raises(ValueError, match="only be attached to one Application"):
        topo.add_process(second)


def test_topology_rejects_configuration_after_start(tmp_path) -> None:
    topo = BluetoothTopology(_env(tmp_path), "sim0", tmp_path / "log")
    controller = topo.add_controller()
    process = ProcessInstance(command=[tmp_path / "firmware"], controller=controller, label="device")
    topo._started = True

    with pytest.raises(RuntimeError, match="cannot modify a topology"):
        topo.add_controller()
    with pytest.raises(RuntimeError, match="cannot modify a topology"):
        topo.add_process(process)
    with pytest.raises(RuntimeError, match="cannot modify a topology"):
        topo.set_channel_attenuation(default_db=50.0)
    with pytest.raises(RuntimeError, match="cannot modify a topology"):
        topo.add_burst_interference(2402.0)


def test_add_wlan_interference_exposes_full_wlan_parameters(tmp_path) -> None:
    topo = BluetoothTopology(_env(tmp_path), "sim0", tmp_path / "log")

    ref = topo.add_wlan_interference(
        center_freq_mhz=2437.0,
        power_dbm=11.0,
        config_set="VideoConf",
        mod_type="WN20",
        windows=[(5, 10)],
        rand_seed=7,
    )

    assert ref.index == 0
    source = topo.bsim.interference_sources[0]
    assert isinstance(source, WlanInterference)
    assert source.center_freq_mhz == 2437.0
    assert source.power_dbm == 11.0
    assert source.config_set == "VideoConf"
    assert source.mod_type == "WN20"
    assert source.windows == [(5, 10)]
    assert source.rand_seed == 7


async def test_setup_hci_skips_capture_when_dump_disabled(tmp_path) -> None:
    topo = BluetoothTopology(_env(tmp_path), "sim0", tmp_path / "log", hci_dump=False)
    exe = tmp_path / "firmware"
    exe.write_text("")
    ctl = _register_process(topo, exe=exe).controller
    ctl.socket_dir.mkdir(parents=True)
    ctl.hci_sock.write_text("")

    await topo._setup_hci()

    assert ctl.hci_sock.exists()
    assert topo._btsnoop_captures == []


async def test_start_keeps_wall_time_without_bsim_clock(tmp_path) -> None:
    topo = BluetoothTopology(_env(tmp_path), "sim0", tmp_path / "log")

    await topo.start()
    try:
        loop = asyncio.get_running_loop()
        assert isinstance(loop, BsimEventLoop)
        assert loop.discrete_clock is None
    finally:
        await topo.stop()


async def test_start_configures_babblesim_hci_dump_before_backend_start(tmp_path, monkeypatch) -> None:
    topo = BluetoothTopology(_env(tmp_path), "sim0", tmp_path / "log")
    exe = tmp_path / "firmware"
    exe.write_text("")
    dev = _register_process(topo, exe=exe, label="dev0")
    seen_hci_dump: list[bool] = []

    class FakeClock:
        now_us = 0
        synchronized = False

        def synchronize(self) -> None:
            assert asyncio.get_running_loop().discrete_clock is None
            self.synchronized = True

        def advance_to_us(self, target_us: int) -> int:
            self.now_us = target_us
            return self.now_us

        def close(self) -> None:
            return None

    def fake_start(pm, log_dir):  # noqa: ANN001, ARG001
        return None

    topo.bsim.clock = FakeClock()
    topo.hci_dump = False
    monkeypatch.setattr(dev, "start", fake_start)
    monkeypatch.setattr(topo.bsim, "wait_for_hci_sockets", lambda: None)
    monkeypatch.setattr(topo.bsim, "wait_for_devices_registered", lambda: None)

    async def fake_setup_hci() -> None:
        return None

    monkeypatch.setattr(topo, "_setup_hci", fake_setup_hci)

    def fake_backend_start(pm, *, log_dir):  # noqa: ANN001, ARG001
        seen_hci_dump.append(topo.bsim.hci_dump)

    monkeypatch.setattr(topo.bsim, "start", fake_backend_start)
    monkeypatch.setattr(topo.bsim, "finish", lambda *, log_dir: None)

    loop = asyncio.get_running_loop()
    assert isinstance(loop, BsimEventLoop)
    await topo.start()
    try:
        assert seen_hci_dump == [False]
        assert loop.discrete_clock is topo.bsim.clock
        assert topo.bsim.clock.synchronized
    finally:
        await topo.stop()
    assert loop.discrete_clock is None


async def test_setup_hci_uses_virtual_controller_btsnoop_socket_capture(tmp_path, monkeypatch) -> None:
    topo = BluetoothTopology(_env(tmp_path), "sim0", tmp_path / "log")
    exe = tmp_path / "firmware"
    exe.write_text("")
    ctl = _register_process(
        topo,
        exe=exe,
        label="dev0",
        log_subdir=Path("devices") / "dev0",
    ).controller
    ctl.socket_dir.mkdir(parents=True)
    ctl.hci_btsnoop_sock.write_text("")
    waited: list[str] = []
    started: list[tuple[Path, Path, float]] = []

    class FakeCapture:
        def __init__(
            self,
            *,
            socket_path,
            output_path,
        ) -> None:
            self.socket_path = socket_path
            self.output_path = output_path

        async def start(self, *, timeout: float) -> None:
            started.append((self.socket_path, self.output_path, timeout))

        async def stop(self) -> None:
            return None

    monkeypatch.setattr(topo.bsim, "wait_for_btsnoop_sockets", lambda: waited.append("wait_btsnoop"))
    monkeypatch.setattr("bsworld.topology.BtsnoopSocketCapture", FakeCapture)

    await topo._setup_hci()

    assert waited == ["wait_btsnoop"]
    assert started == [
        (
            tmp_path / "state" / "sim0" / "hci0.btsnoop.sock",
            tmp_path / "log" / "devices" / "dev0" / "hci0.snoop",
            30.0,
        )
    ]
    assert len(topo._btsnoop_captures) == 1


async def test_setup_hci_captures_in_process_controller_btsnoop(tmp_path, monkeypatch) -> None:
    topo = BluetoothTopology(_env(tmp_path), "sim0", tmp_path / "log")
    ctl = topo.add_controller(
        public_address="C0:FF:EE:00:00:04",
        log_subdir=Path("python") / "bumble",
    )
    ctl.socket_dir.mkdir(parents=True)
    ctl.hci_btsnoop_sock.write_text("")
    started: list[tuple[Path, Path, float]] = []

    class FakeCapture:
        def __init__(
            self,
            *,
            socket_path,
            output_path,
        ) -> None:
            self.socket_path = socket_path
            self.output_path = output_path

        async def start(self, *, timeout: float) -> None:
            started.append((self.socket_path, self.output_path, timeout))

        async def stop(self) -> None:
            return None

    monkeypatch.setattr(topo.bsim, "wait_for_btsnoop_sockets", lambda: None)
    monkeypatch.setattr("bsworld.topology.BtsnoopSocketCapture", FakeCapture)

    await topo._setup_hci()

    assert started == [
        (
            tmp_path / "state" / "sim0" / "hci0.btsnoop.sock",
            tmp_path / "log" / "python" / "bumble" / "hci0.snoop",
            30.0,
        )
    ]
    assert len(topo._btsnoop_captures) == 1


def test_process_command_resolves_after_all_device_ids_are_assigned(tmp_path) -> None:
    topo = BluetoothTopology(_env(tmp_path), "sim0", tmp_path / "log")
    scanner_exe = tmp_path / "scanner"
    advertiser_exe = tmp_path / "advertiser"
    scanner_exe.write_text("")
    advertiser_exe.write_text("")
    _register_process(topo, exe=scanner_exe, label="scanner")
    controller = topo.add_controller()

    def command() -> list[str | Path]:
        return [advertiser_exe, f"--device={controller.application_dev_id}"]

    dev = topo.add_process(
        ProcessInstance(
            command=command,
            controller=controller,
            label="advertiser",
        )
    )
    calls: list[tuple[str, list[str], dict]] = []

    class FakeProc:
        pid = 1234

        def alive(self) -> bool:
            return True

    class FakeProcessManager:
        def spawn(self, name, cmd, **kwargs):
            calls.append((name, [str(part) for part in cmd], kwargs))
            return FakeProc()

    try:
        dev.start(FakeProcessManager(), tmp_path / "log")
    finally:
        dev.stop_capture()

    assert calls[0][1] == [
        str(advertiser_exe),
        "--device=3",
    ]
    assert calls[0][2]["stdin"] is None


def test_process_shell_start_does_not_write_commands(tmp_path) -> None:
    topo = BluetoothTopology(_env(tmp_path), "nuttx_bsim_test1", tmp_path / "log")
    exe = tmp_path / "nuttx"
    exe.write_text("")
    dev = _register_process(
        topo,
        exe=exe,
        label="shell",
        shell=True,
    )
    calls: list[tuple[str, list[str], dict]] = []
    proc_stdin = io.BytesIO()

    class FakePopen:
        stdin = proc_stdin

    class FakeProc:
        pid = 1234
        popen = FakePopen()

        def alive(self) -> bool:
            return True

    class FakeProcessManager:
        def spawn(self, name, cmd, **kwargs):  # noqa: ANN001
            calls.append((name, [str(part) for part in cmd], kwargs))
            return FakeProc()

    try:
        dev.start(FakeProcessManager(), tmp_path / "log")
    finally:
        dev.stop_capture()

    assert calls[0][2]["stdin"] == subprocess.PIPE
    assert proc_stdin.getvalue() == b""


async def test_process_shell_can_send_commands_after_start(tmp_path) -> None:
    topo = BluetoothTopology(_env(tmp_path), "nuttx_bsim_test1", tmp_path / "log")
    exe = tmp_path / "nuttx"
    exe.write_text("")
    dev = _register_process(
        topo,
        exe=exe,
        label="shell",
        shell=True,
    )
    calls: list[tuple[str, list[str], dict]] = []
    proc_stdin = io.BytesIO()

    class FakePopen:
        stdin = proc_stdin

    class FakeProc:
        pid = 1234
        popen = FakePopen()

        def alive(self) -> bool:
            return True

    class FakeProcessManager:
        def spawn(self, name, cmd, **kwargs):  # noqa: ANN001
            calls.append((name, [str(part) for part in cmd], kwargs))
            return FakeProc()

    try:
        dev.start(FakeProcessManager(), tmp_path / "log")
        assert proc_stdin.getvalue() == b""
        await dev.shell.run("ifup bnep0")
        await dev.shell.run("blecent")
    finally:
        dev.stop_capture()

    assert calls[0][2]["stdin"] == subprocess.PIPE
    assert proc_stdin.getvalue() == b"ifup bnep0\nblecent\n"


def test_process_shell_is_disabled_by_default(tmp_path) -> None:
    topo = BluetoothTopology(_env(tmp_path), "nuttx_bsim_test1", tmp_path / "log")
    exe = tmp_path / "nuttx"
    exe.write_text("")
    dev = _register_process(topo, exe=exe)

    assert dev.shell.enabled is False
    with pytest.raises(RuntimeError, match="shell input is not enabled"):
        dev.shell.send("ifup bnep0")


def test_process_start_opens_log_capture(tmp_path, monkeypatch) -> None:
    topo = BluetoothTopology(_env(tmp_path), "sim0", tmp_path / "log")
    exe = tmp_path / "firmware"
    exe.write_text("")
    dev = _register_process(topo, exe=exe, label="dev0")
    opened: list[Path] = []

    class FakePipe:
        write_fd = 99
        log_fh = object()

        def stop(self) -> None:
            return None

        def flush(self) -> None:
            return None

    def fake_open(log_path):  # noqa: ANN001
        opened.append(log_path)
        return FakePipe()

    class FakeProc:
        pid = 1234

    class FakeProcessManager:
        def spawn(self, name, cmd, **kwargs):  # noqa: ANN001
            return FakeProc()

    monkeypatch.setattr("bsworld.devices.instance.LogCapture.open", fake_open)

    try:
        dev.start(FakeProcessManager(), tmp_path / "log")
    finally:
        dev.stop_capture()

    assert opened == [tmp_path / "log" / "dev0.log"]


def test_channel_attenuation_resolves_processes_to_virtual_controllers(tmp_path) -> None:
    topo = BluetoothTopology(_env(tmp_path), "sim0", tmp_path / "log")
    host_exe = tmp_path / "host"
    dev_exe = tmp_path / "device"
    host_exe.write_text("")
    dev_exe.write_text("")
    host = _register_process(
        topo,
        exe=host_exe,
        label="host",
        log_subdir=Path("devices") / "host",
    )
    device = _register_process(
        topo,
        exe=dev_exe,
        label="device",
        log_subdir=Path("devices") / "device",
    )
    jammer = topo.add_burst_interference(2402.0)
    assert [process.controller.controller_dev_id for process in topo.processes] == [0, 1]
    assert [process.controller.application_dev_id for process in topo.processes] == [2, 3]

    topo.set_channel_attenuation(
        default_db=90.0,
        static_paths=[
            StaticAttenuation(tx=host, rx=device, attenuation_db=55.0),
            StaticAttenuation(tx=jammer, rx=device, attenuation_db=20.0),
            StaticAttenuation(tx=jammer, rx=host, attenuation_db=120.0),
        ],
        timed_paths=[
            TimedAttenuation(
                tx=host,
                rx=device,
                times_us=[0, 10],
                attenuation_db=[40.0, 80.0],
            ),
        ],
    )

    topo._resolve_channel_attenuation()

    ca = topo.bsim.channel_attenuation
    assert ca is not None
    assert ca.static_paths == [
        StaticAttenuation(tx=0, rx=1, attenuation_db=55.0),
        StaticAttenuation(tx=5, rx=1, attenuation_db=20.0),
        StaticAttenuation(tx=5, rx=0, attenuation_db=120.0),
    ]
    assert ca.timed_paths == [
        TimedAttenuation(tx=0, rx=1, times_us=[0, 10], attenuation_db=[40.0, 80.0]),
    ]


def test_channel_attenuation_rejects_foreign_controller(tmp_path) -> None:
    topo = BluetoothTopology(_env(tmp_path), "sim0", tmp_path / "log")
    other = BluetoothTopology(_env(tmp_path), "sim1", tmp_path / "other-log")
    local = topo.add_controller()
    foreign = other.add_controller()
    topo.set_channel_attenuation(
        static_paths=[StaticAttenuation(tx=local, rx=foreign, attenuation_db=50.0)],
    )

    with pytest.raises(ValueError, match="does not belong to this topology"):
        topo._resolve_channel_attenuation()


@pytest.mark.parametrize("index", [-1, 0])
def test_channel_attenuation_rejects_unknown_interference_ref(tmp_path, index: int) -> None:
    topo = BluetoothTopology(_env(tmp_path), "sim0", tmp_path / "log")

    with pytest.raises(ValueError, match="unknown interference source ref"):
        topo._resolve_path_endpoint(InterferenceRef(index))


@pytest.mark.parametrize("endpoint", [-1, True, object()])
def test_channel_attenuation_rejects_invalid_raw_endpoint(tmp_path, endpoint: object) -> None:
    topo = BluetoothTopology(_env(tmp_path), "sim0", tmp_path / "log")

    with pytest.raises((TypeError, ValueError), match="attenuation endpoint"):
        topo._resolve_path_endpoint(endpoint)


@pytest.mark.parametrize("cleanup_fails", [False, True])
async def test_stop_finalizes_backend_even_if_process_cleanup_fails(tmp_path, monkeypatch, cleanup_fails) -> None:
    events: list[str] = []
    topo = BluetoothTopology(_env(tmp_path), "sim0", tmp_path / "log")

    class FakeProcessManager:
        def cleanup(self) -> None:
            events.append("cleanup")
            if cleanup_fails:
                raise RuntimeError("cleanup failed")

        def restore_signal_handlers(self) -> None:
            events.append("restore")

    async def fake_to_thread(fn, *args, **kwargs):
        events.append("to_thread")
        return fn(*args, **kwargs)

    topo.pm = FakeProcessManager()
    monkeypatch.setattr("bsworld.topology.asyncio.to_thread", fake_to_thread)
    monkeypatch.setattr(topo.bsim, "finish", lambda *, log_dir: events.append("finish"))

    if cleanup_fails:
        with pytest.raises(RuntimeError, match="cleanup failed"):
            await topo.stop()
    else:
        await topo.stop()

    assert events == ["to_thread", "cleanup", "restore", "finish"]
