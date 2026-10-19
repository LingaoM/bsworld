# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0


import pytest

from bscontroller.linklayer import (
    LL_DATA_CHANNEL_MAP_ALL,
)
from bscontroller.linklayer.channel_selection import channel_selection_2


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
