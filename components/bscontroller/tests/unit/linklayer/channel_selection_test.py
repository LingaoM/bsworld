# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Channel Selection Algorithms #1 and #2 against Core spec sample data.

Checks the data-channel index mapping (Core Vol 6, Part B, 4.5.8):

- ``channel_selection_2`` against the CSA #2 worked examples, including a
  reduced channel map.
- ``channel_selection_1`` against the CSA #1 channel-map-update example, driving
  the unmapped index with the spec's hopIncrement of 10.

These are fixed-vector checks; connection-time use of the algorithms is covered
by the link-layer connection scenarios.
"""

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
    """CSA #2 maps each event counter to the spec's sample channel index.

    Purpose: Verify ``channel_selection_2`` reproduces the Channel Selection
    Algorithm #2 worked examples (Vol 6, Part B, 4.5.8.3), including a case
    with a reduced channel map, using the spec's channelIdentifier 0x305F.

    Steps:
        1. For each parametrized event counter and channel map, call
           ``channel_selection_2`` with channelIdentifier 0x0000305F.

    Expected:
        - The returned data-channel index equals the spec's expected value for
          both the full map and the reduced map 0x1E00E00600.
    """
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
    """CSA #1 maps the spec's update example to its remapped channel index.

    Purpose: Verify ``channel_selection_1`` reproduces the Channel Selection
    Algorithm #1 channel-map-update example (Vol 6, Part B, 4.5.8.1 and 5.1.2),
    where a reduced channel map remaps an unmapped index to a used channel.

    Steps:
        1. Derive the unmapped channel for the event using the spec's
           hopIncrement of 10: ``(event + 1) * 10 mod 37``.
        2. Call ``channel_selection_1`` with that unmapped index and the map.

    Expected:
        - The returned data-channel index equals the spec's expected value for
          the full map and the reduced map 0x1FFFFFF7FF.
    """
    # Core Vol 6, Part B, 5.1.2: hopIncrement 10, first event uses (0 + 10) mod 37.
    unmapped = (event + 1) * 10 % 37
    assert channel_selection_1(unmapped, channel_map) == expected
