# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0


import pytest

from bscontroller.linklayer import (
    LL_DATA_CHANNEL_MAP_ALL,
)
from bscontroller.linklayer.channel_selection import (
    channel_selection_1,
    channel_selection_2,
)


@pytest.mark.parametrize(
    'counter,channel_map,expected',
    [
        (0, LL_DATA_CHANNEL_MAP_ALL, 25),
        (1, LL_DATA_CHANNEL_MAP_ALL, 20),
        (2, LL_DATA_CHANNEL_MAP_ALL, 6),
        (3, LL_DATA_CHANNEL_MAP_ALL, 21),
        (6, 0x1E00E00600, 23),
        (7, 0x1E00E00600, 9),
        (8, 0x1E00E00600, 34),
    ],
)
def test_csa2_core_spec_sample_data(counter, channel_map, expected):
    assert channel_selection_2(counter, 0x0000305F, channel_map) == expected


@pytest.mark.parametrize(
    'event,channel_map,expected',
    [
        (99, LL_DATA_CHANNEL_MAP_ALL, 1),
        (100, 0x1FFFFFF7FF, 12),
        (101, 0x1FFFFFF7FF, 21),
    ],
)
def test_csa1_core_spec_channel_map_update_example(event, channel_map, expected):
    # Core Vol 6, Part B, 5.1.2: hopIncrement 10, first event uses (0 + 10) mod 37.
    unmapped = (event + 1) * 10 % 37
    assert channel_selection_1(unmapped, channel_map) == expected
