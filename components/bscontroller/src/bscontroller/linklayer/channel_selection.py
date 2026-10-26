# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""LE Channel Selection Algorithms #1 and #2 (Core 6.3, Vol 6, Part B, 4.5.8)."""

from bscontroller.linklayer import (
    LL_CHANNEL_ID_BITS,
    LL_CHANNEL_ID_MASK,
    LL_CSA2_MAM_MULTIPLIER,
    LL_CSA2_MAM_ROUNDS,
    LL_DATA_CHANNEL_COUNT,
    LL_EVENT_COUNTER_MASK,
)
from bscontroller.linklayer.parameters import valid_channel_map
from bscontroller.radio.base import PHY_OCTET_BITS, PHY_OCTET_MASK


def channel_selection_1(unmapped_channel: int, channel_map: int) -> int:
    """Core Vol 6, Part B, 4.5.8.2; remap an unused channel by unmappedChannel mod numUsedChannels.

    The caller owns lastUnmappedChannel and its per-event hopIncrement step.
    """
    if channel_map & (1 << unmapped_channel):
        return unmapped_channel
    enabled = [index for index in range(LL_DATA_CHANNEL_COUNT) if channel_map & (1 << index)]
    return enabled[unmapped_channel % len(enabled)]


def channel_selection_2(counter: int, access_address: int, channel_map: int) -> int:
    """Core Vol 6, Part B, 4.5.8.3; ascending channel remapping."""
    if not valid_channel_map(channel_map):
        raise ValueError('invalid channel map')
    channel_id = (access_address >> LL_CHANNEL_ID_BITS) ^ (access_address & LL_CHANNEL_ID_MASK)
    prn = (counter & LL_EVENT_COUNTER_MASK) ^ channel_id
    for _ in range(LL_CSA2_MAM_ROUNDS):
        prn = int(f'{prn >> PHY_OCTET_BITS:0{PHY_OCTET_BITS}b}'[::-1], 2) << PHY_OCTET_BITS | int(
            f'{prn & PHY_OCTET_MASK:0{PHY_OCTET_BITS}b}'[::-1], 2
        )
        prn = (LL_CSA2_MAM_MULTIPLIER * prn + channel_id) & LL_CHANNEL_ID_MASK
    prn ^= channel_id
    unmapped = prn % LL_DATA_CHANNEL_COUNT
    if channel_map & (1 << unmapped):
        return unmapped
    enabled = [index for index in range(LL_DATA_CHANNEL_COUNT) if channel_map & (1 << index)]
    return enabled[(len(enabled) * prn) >> LL_CHANNEL_ID_BITS]
