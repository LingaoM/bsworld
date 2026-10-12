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
"""Unit tests for interference dataclass validation logic."""
from __future__ import annotations

from pathlib import Path

import pytest

from bsworld.interference import (
    BSIM_INTERFERENCE_MAX_WINDOWS,
    BurstInterference,
    ChannelAttenuation,
    PlaybackInterference,
    StaticAttenuation,
    TimedAttenuation,
    WlanInterference,
)


def test_wlan_requires_channel_or_freq() -> None:
    with pytest.raises(ValueError, match="either channel or center_freq_mhz"):
        WlanInterference()


def test_wlan_rejects_both_channel_and_freq() -> None:
    with pytest.raises(ValueError, match="not both"):
        WlanInterference(channel=6, center_freq_mhz=2437.0)


def test_wlan_accepts_channel_only() -> None:
    src = WlanInterference(channel=14)
    assert src.channel == 14
    assert src.center_freq_mhz is None


def test_wlan_accepts_freq_only() -> None:
    src = WlanInterference(center_freq_mhz=2437.0)
    assert src.center_freq_mhz == 2437.0


@pytest.mark.parametrize("channel", [0, 15, 6.5, True])
def test_wlan_rejects_invalid_channel(channel) -> None:
    with pytest.raises(ValueError, match="channel"):
        WlanInterference(channel=channel)


def test_wlan_accepts_extended_config_set() -> None:
    src = WlanInterference(channel=6, config_set="50_24M")
    assert src.config_set == "50_24M"


@pytest.mark.parametrize("config_set", ["", "Browser", "50_11M"])
def test_wlan_rejects_unknown_config_set(config_set) -> None:
    with pytest.raises(ValueError, match="config_set"):
        WlanInterference(channel=6, config_set=config_set)


@pytest.mark.parametrize("mod_type", ["", "WN3", "Prop2M"])
def test_wlan_rejects_unsupported_mod_type(mod_type) -> None:
    with pytest.raises(ValueError, match="mod_type"):
        WlanInterference(channel=6, mod_type=mod_type)


def test_timed_attenuation_requires_matching_lengths() -> None:
    with pytest.raises(ValueError, match="same length"):
        TimedAttenuation(tx=0, rx=1, times_us=[0, 10], attenuation_db=[40.0])


def test_timed_attenuation_requires_at_least_two_points() -> None:
    with pytest.raises(ValueError, match="at least 2 time points"):
        TimedAttenuation(tx=0, rx=1, times_us=[0], attenuation_db=[40.0])


def test_timed_attenuation_requires_strictly_ascending_times() -> None:
    with pytest.raises(ValueError, match="strictly ascending"):
        TimedAttenuation(tx=0, rx=1, times_us=[0, 10, 10], attenuation_db=[1.0, 2.0, 3.0])


def test_timed_attenuation_accepts_valid_points() -> None:
    tp = TimedAttenuation(tx=0, rx=1, times_us=[0, 10, 20], attenuation_db=[40.0, 60.0, 50.0])
    assert tp.times_us == [0, 10, 20]


@pytest.mark.parametrize("times_us", [[0.5, 10], [-1, 10]])
def test_timed_attenuation_rejects_invalid_times(times_us) -> None:
    with pytest.raises(ValueError, match="times_us"):
        TimedAttenuation(tx=0, rx=1, times_us=times_us, attenuation_db=[40.0, 60.0])


def test_timed_attenuation_rejects_non_finite_attenuation() -> None:
    with pytest.raises(ValueError, match="attenuation_db"):
        TimedAttenuation(tx=0, rx=1, times_us=[0, 10], attenuation_db=[40.0, float("nan")])


def test_channel_attenuation_rejects_matrix_file_with_generated_paths() -> None:
    with pytest.raises(ValueError, match="either matrix_file or generated paths"):
        ChannelAttenuation(
            matrix_file=Path("matrix.txt"),
            static_paths=[StaticAttenuation(tx=0, rx=1, attenuation_db=50.0)],
        )


def test_channel_attenuation_allows_matrix_file_alone() -> None:
    ca = ChannelAttenuation(matrix_file=Path("matrix.txt"))
    assert ca.matrix_file == Path("matrix.txt")


def test_channel_attenuation_defaults() -> None:
    ca = ChannelAttenuation()
    assert ca.default_attenuation_db == 60.0
    assert ca.static_paths == []
    assert ca.timed_paths == []


@pytest.mark.parametrize(
    ("kwargs", "field"),
    [
        ({"default_attenuation_db": -101.0}, "default_attenuation_db"),
        ({"default_attenuation_db": 101.0}, "default_attenuation_db"),
        ({"extra_attenuation_db": -101.0}, "extra_attenuation_db"),
        ({"extra_attenuation_db": 101.0}, "extra_attenuation_db"),
    ],
)
def test_channel_attenuation_rejects_bsim_cli_out_of_range(kwargs, field) -> None:
    with pytest.raises(ValueError, match=field):
        ChannelAttenuation(**kwargs)


def test_burst_interference_defaults() -> None:
    burst = BurstInterference(center_freq_mhz=2402.0)
    assert burst.power_dbm == 20.0
    assert burst.interf_type == "CW"
    assert burst.windows == []


@pytest.mark.parametrize("center_freq_mhz", [2273.0, 2527.0, 2402.5])
def test_burst_interference_frequency_range(center_freq_mhz) -> None:
    if center_freq_mhz == 2402.5:
        assert BurstInterference(center_freq_mhz=center_freq_mhz).center_freq_mhz == center_freq_mhz
    else:
        with pytest.raises(ValueError, match="center_freq_mhz"):
            BurstInterference(center_freq_mhz=center_freq_mhz)


@pytest.mark.parametrize("power_dbm", [-129.0, 128.0, float("inf")])
def test_burst_interference_rejects_invalid_power(power_dbm) -> None:
    with pytest.raises(ValueError, match="power_dbm"):
        BurstInterference(center_freq_mhz=2402.0, power_dbm=power_dbm)


@pytest.mark.parametrize("interf_type", ["", "WN3", "BLI", "Prop2M"])
def test_burst_interference_rejects_unsupported_type(interf_type) -> None:
    with pytest.raises(ValueError, match="interf_type"):
        BurstInterference(center_freq_mhz=2402.0, interf_type=interf_type)


@pytest.mark.parametrize(
    "windows",
    [
        [(0, 1)],
        [(1, 1)],
        [(1, 3), (3, 4)],
        [(1, 3), (2, 4)],
        [(1.5, 3)],
    ],
)
def test_burst_interference_rejects_invalid_windows(windows) -> None:
    with pytest.raises(ValueError, match="windows"):
        BurstInterference(center_freq_mhz=2402.0, windows=windows)


def test_burst_interference_rejects_too_many_windows() -> None:
    windows = [(i * 2 + 1, i * 2 + 2) for i in range(BSIM_INTERFERENCE_MAX_WINDOWS + 1)]
    with pytest.raises(ValueError, match="at most"):
        BurstInterference(center_freq_mhz=2402.0, windows=windows)


def test_burst_interference_rejects_invalid_random_seed() -> None:
    with pytest.raises(ValueError, match="rand_seed"):
        BurstInterference(center_freq_mhz=2402.0, rand_seed=-1)


def test_static_attenuation_rejects_non_finite_value() -> None:
    with pytest.raises(ValueError, match="attenuation_db"):
        StaticAttenuation(tx=0, rx=1, attenuation_db=float("nan"))


def test_playback_interference_defaults_enable_all_streams() -> None:
    pb = PlaybackInterference(input_file=Path("cap"))
    assert (pb.tx, pb.rx, pb.rssi, pb.cca) == (True, True, True, True)
