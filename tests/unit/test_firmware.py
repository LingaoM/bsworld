# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Complete firmware identity, radio paths and coexistence with HCI Hosts."""

import pytest
from tests.unit.helpers import register_process

from bsworld.devices import ProcessInstance
from bsworld.interference import StaticAttenuation
from bsworld.topology import BluetoothTopology


def _register_firmware(topo, name):
    return topo.add_process(ProcessInstance(command=["/firmware"], label=name))


def test_two_firmwares_need_only_two_radios_and_the_test_clock(tmp_path, unit_env):
    topo = BluetoothTopology(unit_env, "sim", tmp_path / "log")
    first = _register_firmware(topo, "first")
    second = _register_firmware(topo, "second")
    layout = topo.bsim.plan_devices()

    assert topo.bsim.controllers == []
    assert layout.application_slot(first).dev_id == 0
    assert layout.application_slot(second).dev_id == 1
    assert layout.application_slot(first).sim_id == "sim"
    assert layout.application_slot(first).hci_sock is None
    assert layout.clock_dev_id == 2
    assert layout.device_count == 3
    assert first.log_subdir != second.log_subdir


def test_mixed_topology_resolves_radios_and_interference_without_aliasing(
    tmp_path, unit_env
):
    topo = BluetoothTopology(unit_env, "sim", tmp_path / "log")
    host = register_process(topo, exe="/host", label="host")
    complete = _register_firmware(topo, "complete")
    jammer = topo.add_burst_interference(2402.0)
    topo.set_channel_attenuation(
        static_paths=[
            StaticAttenuation(tx=host, rx=complete, attenuation_db=45),
            StaticAttenuation(tx=jammer, rx=complete, attenuation_db=10),
        ]
    )
    topo._resolve_channel_attenuation()
    layout = topo.bsim.plan_devices()

    assert layout.application_slot(host).dev_id == 1
    assert layout.application_slot(complete).dev_id == 2
    assert layout.clock_dev_id == 3
    assert layout.device_count == 5
    assert topo.bsim.channel_attenuation.static_paths == [
        StaticAttenuation(tx=0, rx=2, attenuation_db=45),
        StaticAttenuation(tx=4, rx=2, attenuation_db=10),
    ]


def test_foreign_firmware_cannot_alias_a_local_radio(tmp_path, unit_env):
    topo = BluetoothTopology(unit_env, "sim", tmp_path / "log")
    other = BluetoothTopology(unit_env, "other", tmp_path / "other")
    _register_firmware(topo, "local")
    foreign = _register_firmware(other, "foreign")
    with pytest.raises(ValueError, match="does not belong"):
        topo.bsim.plan_devices().resolve_endpoint(foreign)


@pytest.mark.parametrize("participant", ["firmware", "controller", "interference"])
def test_frozen_firmware_layout_rejects_late_radio_registrations(
    tmp_path, unit_env, participant
):
    topo = BluetoothTopology(unit_env, "sim", tmp_path / "log")
    _register_firmware(topo, "first")
    layout = topo.bsim.plan_devices()
    with pytest.raises(RuntimeError, match="frozen"):
        if participant == "firmware":
            _register_firmware(topo, "second")
        elif participant == "controller":
            topo.add_controller()
        else:
            topo.add_burst_interference(2402)
    assert topo.bsim.plan_devices() is layout
    assert layout.device_count == 2
