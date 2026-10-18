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

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from bsworld.backends import babblesim
from bsworld.backends.babblesim import BabbleSimBackend
from bsworld.env import Env
from bsworld.interference import (
    BurstInterference,
    PlaybackInterference,
    StaticAttenuation,
    TimedAttenuation,
    WlanInterference,
)


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


class _SpawnRecorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str], dict]] = []

    def spawn(self, name, cmd, **kwargs):  # noqa: ARG002
        self.calls.append((name, [str(part) for part in cmd], kwargs))
        return SimpleNamespace(alive=lambda: True)


def _patch_controller_bin(monkeypatch, tmp_path: Path) -> Path:
    controller = tmp_path / "build" / "hci" / "bt_virt_controller"
    controller.parent.mkdir(parents=True, exist_ok=True)
    controller.write_text("#!/bin/sh\n")
    controller.chmod(0o755)
    monkeypatch.setattr(babblesim.hci_virt_build, "controller_bin", lambda env: controller)
    return controller


def _add_process_controller(backend: BabbleSimBackend):
    controller = backend.add_controller()
    backend.reserve_application_device(controller)
    return controller


def test_interference_argv_builders_cover_burst_wlan_and_playback(tmp_path) -> None:
    bin_dir = tmp_path / "bin"

    burst = babblesim._build_interf_argv(
        BurstInterference(2402.0, power_dbm=5, interf_type="CW", windows=[(1, 2)], rand_seed=7),
        sim_id="sim",
        dev_id=3,
        bin_dir=bin_dir,
    )
    wlan = babblesim._build_interf_argv(
        WlanInterference(channel=6, config_set="VideoConf", rand_seed=9),
        sim_id="sim",
        dev_id=4,
        bin_dir=bin_dir,
    )
    playback = babblesim._build_interf_argv(
        PlaybackInterference(input_file=Path("capture"), rx=False, cca=False),
        sim_id="sim",
        dev_id=5,
        bin_dir=bin_dir,
    )

    assert burst == [
        bin_dir / "bs_device_2G4_burst_interf",
        "-s=sim",
        "-d=3",
        "-centerfreq=2402.0",
        "-power=5",
        "-type=CW",
        "-rs=7",
        "-timestart",
        "1",
        "-timeend",
        "2",
    ]
    assert "-channel=6" in wlan
    assert "-ConfigSet=VideoConf" in wlan
    assert "-rs=9" in wlan
    assert playback[-2:] == ["-rxoff", "-ccaoff"]


def test_write_timed_matrix_keeps_partial_paths_inspectable(tmp_path) -> None:
    matrix = babblesim._write_attenuation_matrix(
        static_paths=[],
        timed_paths=[TimedAttenuation(tx=0, rx=1, times_us=[0, 10], attenuation_db=[40.0, 80.0])],
        out_dir=tmp_path,
    )

    timed_file = tmp_path / "timed_att_0_1_0.txt"
    assert matrix.read_text() == f'0 1 : "{timed_file}"\n'
    assert timed_file.read_text() == "0    40.0\n10    80.0\n"


def test_write_attenuation_matrix_supports_static_and_timed_paths(tmp_path) -> None:
    matrix = babblesim._write_attenuation_matrix(
        static_paths=[
            StaticAttenuation(tx=2, rx=1, attenuation_db=20.0),
            StaticAttenuation(tx=2, rx=0, attenuation_db=120.0),
        ],
        timed_paths=[
            TimedAttenuation(tx=0, rx=1, times_us=[0, 10], attenuation_db=[40.0, 80.0]),
        ],
        out_dir=tmp_path,
    )

    timed_file = tmp_path / "timed_att_0_1_0.txt"
    assert matrix.read_text() == (
        "2 1 : 20.0\n"
        "2 0 : 120.0\n"
        f'0 1 : "{timed_file}"\n'
    )
    assert timed_file.read_text() == "0    40.0\n10    80.0\n"


def test_check_deps_ready_only_validates_built_artifacts(tmp_path, monkeypatch) -> None:
    env = _env(tmp_path)
    backend = BabbleSimBackend(env, "sim")
    calls: list[str] = []

    monkeypatch.setattr(babblesim.bsim_build, "check_ready", lambda build_env: calls.append(f"bsim:{build_env is env}"))
    monkeypatch.setattr(babblesim.hci_virt_build, "check_ready", lambda build_env: calls.append(f"hci:{build_env is env}"))

    backend.check_deps_ready()

    assert calls == ["bsim:True", "hci:True"]


def test_add_controller_rejects_started_backend(tmp_path) -> None:
    backend = BabbleSimBackend(_env(tmp_path), "sim")
    backend.start(_SpawnRecorder())

    with pytest.raises(RuntimeError, match="after BabbleSim has started"):
        backend.add_controller()


def test_start_spawns_phy_virtual_controllers_and_interference(tmp_path, monkeypatch) -> None:
    env = _env(tmp_path)
    backend = BabbleSimBackend(env, "sim")
    backend.check_deps_ready = lambda: None
    backend.prepare = lambda: None
    _add_process_controller(backend)
    _add_process_controller(backend)
    backend.interference_sources.append(BurstInterference(2402.0))
    recorder = _SpawnRecorder()

    _patch_controller_bin(monkeypatch, tmp_path)
    monkeypatch.setattr(babblesim, "wait_for_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(babblesim, "wait_for_paths", lambda *args, **kwargs: None)

    backend.start(recorder, log_dir=tmp_path / "log")

    names = [name for name, _, _ in recorder.calls]
    assert names == [
        "bs_2G4_phy_v1",
        "bt_virt_controller_hci0",
        "bt_virt_controller_hci1",
        "interf_5",
    ]
    assert "-D=6" in recorder.calls[0][1]
    assert "-defmodem=BLE_simple" in recorder.calls[0][1]
    assert backend.clock is not None
    assert backend.clock.dev_id == 4
    assert backend.clock.sim_dir == env.sim_dir("sim")
    assert backend.clock.phy_alive()
    assert "-d=0" in recorder.calls[1][1]
    assert f"-hci-socket={tmp_path / 'state' / 'sim' / 'hci0.sock'}" in recorder.calls[1][1]
    assert f"-btsnoop-socket={tmp_path / 'state' / 'sim' / 'hci0.btsnoop.sock'}" in recorder.calls[1][1]
    assert "-d=1" in recorder.calls[2][1]
    assert f"-hci-socket={tmp_path / 'state' / 'sim' / 'hci1.sock'}" in recorder.calls[2][1]
    assert f"-btsnoop-socket={tmp_path / 'state' / 'sim' / 'hci1.btsnoop.sock'}" in recorder.calls[2][1]
    assert "-d=5" in recorder.calls[3][1]
    log_dirs = {name: kwargs["log_dir"] for name, _, kwargs in recorder.calls}
    assert log_dirs["bs_2G4_phy_v1"] == tmp_path / "log" / "babblesim"
    assert log_dirs["bt_virt_controller_hci0"] == tmp_path / "log" / "bt_virt_controller"
    assert log_dirs["bt_virt_controller_hci1"] == tmp_path / "log" / "bt_virt_controller"
    assert log_dirs["interf_5"] == tmp_path / "log" / "babblesim"
    assert all("nice" not in kwargs for _, _, kwargs in recorder.calls)


def test_start_passes_public_address_to_virtual_controller(tmp_path, monkeypatch) -> None:
    env = _env(tmp_path)
    backend = BabbleSimBackend(env, "sim")
    backend.check_deps_ready = lambda: None
    backend.prepare = lambda: None
    ctl = backend.add_controller()
    ctl.public_address = "C0:FF:EE:00:00:01"
    recorder = _SpawnRecorder()

    _patch_controller_bin(monkeypatch, tmp_path)
    monkeypatch.setattr(babblesim, "wait_for_path", lambda *args, **kwargs: None)

    backend.start(recorder, log_dir=tmp_path / "log")

    controller_args = recorder.calls[1][1]
    assert "-bd-addr=C0:FF:EE:00:00:01" in controller_args


def test_start_places_default_modem_before_channel_plugin_args(tmp_path, monkeypatch) -> None:
    env = _env(tmp_path)
    backend = BabbleSimBackend(env, "sim")
    backend.check_deps_ready = lambda: None
    backend.prepare = lambda: None
    backend.add_controller()
    backend.channel_attenuation = babblesim.ChannelAttenuation(default_attenuation_db=70.0)
    recorder = _SpawnRecorder()

    _patch_controller_bin(monkeypatch, tmp_path)
    monkeypatch.setattr(babblesim, "wait_for_path", lambda *args, **kwargs: None)

    backend.start(recorder, log_dir=tmp_path / "log")

    phy_args = recorder.calls[0][1]
    assert phy_args.index("-defmodem=BLE_simple") < phy_args.index("-argschannel")
    assert "-channel=multiatt" in phy_args
    assert "-argsmain" in phy_args


def test_start_omits_virtual_controller_btsnoop_socket_when_hci_dump_disabled(
    tmp_path,
    monkeypatch,
) -> None:
    env = _env(tmp_path)
    backend = BabbleSimBackend(env, "sim", hci_dump=False)
    backend.check_deps_ready = lambda: None
    backend.prepare = lambda: None
    backend.add_controller()
    recorder = _SpawnRecorder()

    _patch_controller_bin(monkeypatch, tmp_path)
    monkeypatch.setattr(babblesim, "wait_for_path", lambda *args, **kwargs: None)

    backend.start(recorder, log_dir=tmp_path / "log")

    controller_args = recorder.calls[1][1]
    assert f"-hci-socket={tmp_path / 'state' / 'sim' / 'hci0.sock'}" in controller_args
    assert not any(arg.startswith("-btsnoop-socket=") for arg in controller_args)


def test_device_lock_paths_cover_applications_and_interference_devices(tmp_path) -> None:
    env = _env(tmp_path)
    backend = BabbleSimBackend(env, "sim")
    _add_process_controller(backend)
    _add_process_controller(backend)
    backend.interference_sources.append(BurstInterference(2402.0))

    assert backend.device_lock_paths() == [
        tmp_path / "state" / "sim" / "2G4.d0.lock",
        tmp_path / "state" / "sim" / "2G4.d1.lock",
        tmp_path / "state" / "sim" / "2G4.d2.lock",
        tmp_path / "state" / "sim" / "2G4.d3.lock",
        tmp_path / "state" / "sim" / "2G4.d4.lock",
        tmp_path / "state" / "sim" / "2G4.d5.lock",
    ]


def test_registration_connects_clock_before_waiting_for_all_device_locks(tmp_path, monkeypatch) -> None:
    backend = BabbleSimBackend(_env(tmp_path), "sim")
    backend.add_controller()
    calls = []

    class Clock:
        dev_id = 1

        def connect(self, *, timeout):
            calls.append(("connect", timeout))

    backend.clock = Clock()
    monkeypatch.setattr(
        babblesim, "wait_for_paths",
        lambda paths, *, timeout: calls.append((paths, timeout)),
    )
    backend.wait_for_devices_registered(timeout=5)
    assert calls == [
        ("connect", 5),
        (backend.device_lock_paths(), 5),
    ]


def test_registration_does_not_wait_for_locks_after_clock_connection_failure(tmp_path, monkeypatch) -> None:
    backend = BabbleSimBackend(_env(tmp_path), "sim")
    backend.add_controller()

    class Clock:
        dev_id = 1

        def connect(self, *, timeout):
            raise TimeoutError("clock connection failed")

    backend.clock = Clock()
    monkeypatch.setattr(babblesim, "wait_for_paths", lambda *args, **kwargs: pytest.fail("clock not connected"))
    with pytest.raises(TimeoutError, match="clock connection failed"):
        backend.wait_for_devices_registered(timeout=0)


def test_device_lock_paths_skip_in_process_host_slots(tmp_path) -> None:
    env = _env(tmp_path)
    backend = BabbleSimBackend(env, "sim")
    ctl0 = backend.add_controller()
    ctl1 = backend.add_controller()
    backend.interference_sources.append(BurstInterference(2402.0))

    assert ctl0.application_dev_id is None
    assert ctl1.application_dev_id is None
    assert backend.interference_dev_id(0) == 3
    assert backend.device_lock_paths() == [
        tmp_path / "state" / "sim" / "2G4.d0.lock",
        tmp_path / "state" / "sim" / "2G4.d1.lock",
        tmp_path / "state" / "sim" / "2G4.d2.lock",
        tmp_path / "state" / "sim" / "2G4.d3.lock",
    ]


def test_device_ids_support_native_and_in_process_hosts_together(tmp_path) -> None:
    backend = BabbleSimBackend(_env(tmp_path), "sim")
    python_host = backend.add_controller()
    native_host = backend.add_controller()
    backend.reserve_application_device(native_host)
    backend.interference_sources.append(BurstInterference(2402.0))

    assert python_host.controller_dev_id == 0
    assert python_host.application_dev_id is None
    assert native_host.controller_dev_id == 1
    assert native_host.application_dev_id == 2
    assert backend.interference_dev_id(0) == 4
    assert backend.device_lock_paths() == [
        tmp_path / "state" / "sim" / "2G4.d0.lock",
        tmp_path / "state" / "sim" / "2G4.d1.lock",
        tmp_path / "state" / "sim" / "2G4.d2.lock",
        tmp_path / "state" / "sim" / "2G4.d3.lock",
        tmp_path / "state" / "sim" / "2G4.d4.lock",
    ]


@pytest.mark.parametrize("close_fails", [False, True])
def test_finish_releases_clock_before_artifacts_even_if_close_fails(tmp_path, monkeypatch, close_fails) -> None:
    backend = BabbleSimBackend(_env(tmp_path), "sim")
    backend.add_controller()
    calls = []
    warnings = []

    class Clock:
        def close(self):
            calls.append("close")
            if close_fails:
                raise RuntimeError("close failed")

    backend.clock = Clock()
    monkeypatch.setattr(babblesim, "warn", warnings.append)
    monkeypatch.setattr(backend, "convert_ellisys", lambda **kwargs: calls.append("convert"))
    monkeypatch.setattr(backend, "cleanup_sim_artifacts", lambda: calls.append("cleanup"))
    backend.finish(log_dir=tmp_path / "log")

    assert calls == ["close", "convert", "cleanup"]
    assert backend.clock is None
    assert warnings == (["simulation clock close failed: close failed"] if close_fails else [])
    backend.finish(log_dir=tmp_path / "log")
    assert calls.count("close") == 1


def test_finish_releases_clock_after_partial_start_without_controllers(tmp_path) -> None:
    backend = BabbleSimBackend(_env(tmp_path), "sim")
    calls = []

    class Clock:
        def close(self):
            calls.append("close")

    backend.clock = Clock()
    backend.finish()
    assert calls == ["close"]
    assert backend.clock is None


def test_finish_skips_ellisys_conversion_when_disabled(tmp_path) -> None:
    env = _env(tmp_path)
    env = Env(
        out_tag=env.out_tag,
        run_uid=env.run_uid,
        out_dir=env.out_dir,
        log_dir=env.log_dir,
        babblesim_root=env.babblesim_root,
        hci_virt_bin=env.hci_virt_bin,
        bsim_dir=env.bsim_dir,
        bsim_bin_dir=env.bsim_bin_dir,
        bs_state_dir=env.bs_state_dir,
        bsim_ellisys=False,
    )
    backend = BabbleSimBackend(env, "sim")
    backend.add_controller()
    calls: list[str] = []
    backend.convert_ellisys = lambda **kwargs: calls.append("convert")
    backend.cleanup_sim_artifacts = lambda: calls.append("cleanup")

    backend.finish(log_dir=tmp_path / "log")

    assert calls == ["cleanup"]


@pytest.mark.parametrize("image_script", [False, True])
def test_convert_ellisys_writes_trace_under_babblesim_log_dir(tmp_path, monkeypatch, image_script) -> None:
    env = _env(tmp_path)
    converter = (
        env.babblesim_components_dir
        / "ext_2G4_phy_v1"
        / "dump_post_process"
        / "convert_results_to_ellisysv2.sh"
    )
    if image_script:
        converter = tmp_path / "image" / "convert_results_to_ellisysv2.sh"
        env = replace(env, bsim_ellisys_script=converter)
    converter.parent.mkdir(parents=True)
    converter.write_text("#!/bin/sh\n")
    results_dir = env.bsim_dir / "results" / "sim"
    results_dir.mkdir(parents=True)
    tx_file = results_dir / "d_2G4_0.Tx.csv"
    tx_file.write_text("tx\n")
    backend = BabbleSimBackend(env, "sim")

    def fake_run(cmd, *, cwd, stdout):
        assert cmd == ["bash", str(converter), str(tx_file)]
        assert cwd == str(converter.parent)
        stdout.write("trace\n")

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(babblesim.subprocess, "run", fake_run)

    backend.convert_ellisys(log_dir=tmp_path / "log")

    assert (tmp_path / "log" / "babblesim" / "ellisys.bttrp").read_text() == "trace\n"
