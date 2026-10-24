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
"""Immutable BabbleSim device identity layout tests."""

from dataclasses import FrozenInstanceError

import pytest

from bsworld.devices import ProcessInstance, ZephyrController
from bsworld.devices.layout import AppSlot, build_device_layout
from bsworld.interference import InterferenceRef


def _controllers(tmp_path):
    return [
        ZephyrController(index, "sim", "2G4", tmp_path)
        for index in range(2)
    ]


def test_layout_assigns_mixed_participants_once(tmp_path) -> None:
    python_host, native_host = _controllers(tmp_path)

    layout = build_device_layout(
        phy_id="2G4",
        controllers=[python_host, native_host],
        application_controllers=[native_host],
        interference_count=1,
    )

    assert layout.controller_dev_id(python_host) == 0
    assert layout.controller_dev_id(native_host) == 1
    assert layout.application_slot(native_host) == AppSlot(
        sim_id="sim",
        phy_id="2G4",
        dev_id=2,
        hci_sock=tmp_path / "hci1.sock",
    )
    assert layout.clock_dev_id == 3
    assert layout.interference_dev_id(0) == 4
    assert layout.device_count == 5
    assert layout.lock_paths(tmp_path) == [tmp_path / f"2G4.d{index}.lock" for index in range(5)]

    with pytest.raises(KeyError, match="no Application device reserved"):
        layout.application_slot(python_host)
    with pytest.raises(FrozenInstanceError):
        layout.clock_dev_id = 9
    with pytest.raises(TypeError):
        layout.application_slots[0] = None


def test_layout_resolves_declared_rf_endpoints_by_identity(tmp_path) -> None:
    first, second = _controllers(tmp_path)
    process = ProcessInstance(command=[tmp_path / "device"], controller=second, label="device")
    layout = build_device_layout(
        phy_id="2G4",
        controllers=[first, second],
        application_controllers=[second],
        interference_count=1,
    )

    assert layout.resolve_endpoint(7) == 7
    assert layout.resolve_endpoint(first) == 0
    assert layout.resolve_endpoint(process) == 1
    assert layout.resolve_endpoint(InterferenceRef(0)) == 4


@pytest.mark.parametrize("index", [-1, 1])
def test_layout_rejects_unknown_interference(index, tmp_path) -> None:
    controllers = _controllers(tmp_path)
    layout = build_device_layout(
        phy_id="2G4",
        controllers=controllers,
        application_controllers=[],
        interference_count=1,
    )

    with pytest.raises(ValueError, match="unknown interference"):
        layout.resolve_endpoint(InterferenceRef(index))


@pytest.mark.parametrize("endpoint", [-1, True, object()])
def test_layout_rejects_invalid_raw_endpoint(tmp_path, endpoint: object) -> None:
    layout = build_device_layout(
        phy_id="2G4",
        controllers=_controllers(tmp_path),
        application_controllers=[],
        interference_count=0,
    )

    with pytest.raises((TypeError, ValueError), match="attenuation endpoint"):
        layout.resolve_endpoint(endpoint)


def test_layout_rejects_controller_from_another_topology(tmp_path) -> None:
    local, foreign = _controllers(tmp_path)
    layout = build_device_layout(
        phy_id="2G4",
        controllers=[local],
        application_controllers=[],
        interference_count=0,
    )

    with pytest.raises(ValueError, match="does not belong to this topology"):
        layout.resolve_endpoint(foreign)
