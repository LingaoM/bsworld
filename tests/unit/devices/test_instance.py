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
"""Application process startup and resource ownership tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.unit.helpers import register_process, slot_for

from bsworld.devices.instance import ProcessInstance
from bsworld.devices.layout import AppSlot
from bsworld.env import Env
from bsworld.topology import BluetoothTopology


def test_command_factory_receives_the_frozen_application_slot(tmp_path, unit_env: Env, spawn_recorder) -> None:
    topo = BluetoothTopology(unit_env, "sim0", tmp_path / "log")
    scanner = tmp_path / "scanner"
    advertiser = tmp_path / "advertiser"
    scanner.touch()
    advertiser.touch()
    register_process(topo, exe=scanner, label="scanner")
    controller = topo.add_controller()

    def command(slot: AppSlot) -> list[str | Path]:
        return [advertiser, f"--device={slot.dev_id}", f"--phy={slot.phy_id}", f"--sim={slot.sim_id}"]

    process = topo.add_process(ProcessInstance(command=command, controller=controller, label="advertiser"))
    try:
        process.start(spawn_recorder, tmp_path / "log", slot_for(topo, process))
    finally:
        process.stop_capture()

    assert spawn_recorder.calls[0][1] == [
        str(advertiser),
        "--device=3",
        "--phy=2G4",
        "--sim=sim0",
    ]
    assert spawn_recorder.calls[0][2]["stdin"] is None


def test_shell_start_attaches_stdin_without_sending_commands(tmp_path, unit_env: Env, spawn_recorder) -> None:
    topo = BluetoothTopology(unit_env, "sim0", tmp_path / "log")
    executable = tmp_path / "device"
    executable.touch()
    process = register_process(topo, exe=executable, shell=True)
    try:
        process.start(spawn_recorder, tmp_path / "log", slot_for(topo, process))
    finally:
        process.stop_capture()

    assert spawn_recorder.calls[0][2]["stdin"] == subprocess.PIPE
    assert spawn_recorder.stdin.getvalue() == b""


def test_process_shell_is_disabled_by_default(tmp_path, unit_env: Env) -> None:
    topo = BluetoothTopology(unit_env, "sim0", tmp_path / "log")
    controller = topo.add_controller()

    process = ProcessInstance(command=[tmp_path / "device"], controller=controller, label="device")

    assert process.shell.enabled is False


def test_process_start_opens_capture_in_its_log_directory(tmp_path, unit_env: Env, spawn_recorder, monkeypatch) -> None:
    topo = BluetoothTopology(unit_env, "sim0", tmp_path / "log")
    executable = tmp_path / "device"
    executable.touch()
    process = register_process(topo, exe=executable, label="dev0", log_subdir="devices/dev0")
    opened = []

    class FakeCapture:
        write_fd = 99
        log_fh = object()

        def stop(self) -> None:
            return None

    def fake_open(log_path):
        opened.append(log_path)
        return FakeCapture()

    monkeypatch.setattr("bsworld.devices.instance.LogCapture.open", fake_open)
    try:
        process.start(spawn_recorder, tmp_path / "log", slot_for(topo, process))
    finally:
        process.stop_capture()

    assert opened == [tmp_path / "log" / "devices" / "dev0" / "dev0.log"]
