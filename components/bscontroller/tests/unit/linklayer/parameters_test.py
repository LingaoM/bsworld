# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Connection wire vectors and strict timing/channel-map boundaries.

Covers CONNECT_IND parameter encoding and validation (Core Vol 6, Part B,
2.3.3.1):

- ``valid_channel_map`` requires at least two used data channels within range.
- ``valid_timing`` enforces interval, latency and supervision-timeout ranges
  and their interdependence.
- ``Parameters.encode``/``decode`` round-trip the fixed little-endian field
  layout (including the packed SCA/hop octet) and reject truncated, oversized
  or out-of-range fields.

Uses the fixed ``PARAMETERS`` vector from ``tests.unit.helpers``; it is a wire
vector for isolated checks, not the Controller's runtime defaults.
"""

from dataclasses import replace

import pytest

from bscontroller.linklayer import (
    LL_CONN_INTERVAL_MAX,
    LL_CONN_INTERVAL_MIN,
    LL_CONN_LATENCY_MAX,
    LL_CONN_WINDOW_SIZE_MAX,
    LL_CONN_WINDOW_SIZE_MIN,
    LL_DATA_CHANNEL_COUNT,
    LL_HOP_INCREMENT_MAX,
    LL_HOP_INCREMENT_MIN,
    LL_SUPERVISION_TIMEOUT_MAX,
    LL_SUPERVISION_TIMEOUT_MIN,
    PDU_ADV_ACCESS_ADDRESS,
    PDU_ADV_CONNECT_DATA_SIZE,
)
from bscontroller.linklayer.parameters import (
    Parameters,
    valid_channel_map,
    valid_timing,
)
from tests.unit.helpers import PARAMETERS


@pytest.mark.parametrize(
    'value,expected',
    [
        (0, False),
        (1, False),
        (3, True),
        ((1 << (LL_DATA_CHANNEL_COUNT - 1)) | 1, True),
        (1 << LL_DATA_CHANNEL_COUNT | 3, False),
        (-1, False),
    ],
)
def test_channel_map_validation(value, expected):
    """Channel-map validation requires two or more in-range used channels.

    Purpose: Verify ``valid_channel_map`` accepts a map only when it has at
    least two used data channels and no bit set outside the data-channel range
    (Vol 6, Part B, 2.3.3.1).

    Steps:
        1. For each parametrized channel-map value, call ``valid_channel_map``.

    Expected:
        - Maps with fewer than two channels, bits above the channel count, or
          negative values are rejected; two-or-more in-range channels pass.
    """
    assert valid_channel_map(value) == expected


@pytest.mark.parametrize(
    'timing,expected',
    [
        (
            (LL_CONN_INTERVAL_MIN, LL_CONN_INTERVAL_MAX, 0, LL_SUPERVISION_TIMEOUT_MAX),
            True,
        ),
        ((LL_CONN_INTERVAL_MIN - 1, LL_CONN_INTERVAL_MIN, 0, 100), False),
        ((24, 23, 0, 100), False),
        ((24, 24, LL_CONN_LATENCY_MAX + 1, LL_SUPERVISION_TIMEOUT_MAX), False),
        ((24, 24, 0, 6), False),
        ((24, 24, 0, LL_SUPERVISION_TIMEOUT_MIN), True),
        ((24, 24, 1, 12), False),
    ],
)
def test_connection_timing_validation(timing, expected):
    """Connection timing validation enforces ranges and their interdependence.

    Purpose: Verify ``valid_timing`` accepts (interval_min, interval_max,
    latency, timeout) only when each is in range and the combination is
    consistent, in particular the supervision-timeout vs interval-and-latency
    relationship (Vol 6, Part B, 4.5.2).

    Steps:
        1. For each parametrized timing tuple, call ``valid_timing``.

    Expected:
        - Out-of-range interval, excessive latency, too-small timeout and
          inconsistent latency/timeout combinations are rejected; valid tuples
          pass.
    """
    assert valid_timing(*timing) == expected


def test_connect_ind_uses_fixed_little_endian_fields_and_packed_sca():
    """CONNECT_IND encodes fixed little-endian fields and round-trips exactly.

    Purpose: Verify ``Parameters.encode`` lays out the CONNECT_IND LLData with
    the spec's little-endian fields and packs SCA and hop into one octet, and
    that ``Parameters.decode`` recovers the same values (Vol 6, Part B,
    2.3.3.1).

    Steps:
        1. Build parameters from the fixed vector with CRCInit 0xABCDEF,
           window offset 2 and SCA 5.
        2. Encode and compare to the known 22-octet wire string.
        3. Decode the wire string back to parameters.

    Expected:
        - The encoding is exactly the expected 22 octets
          (``PDU_ADV_CONNECT_DATA_SIZE``).
        - Decoding reproduces the original parameters.
    """
    parameters = replace(PARAMETERS, crc_init=0xABCDEF, window_offset=2, sca=5)
    wire = bytes.fromhex('7083329aefcdab010200180000006400ffffffff1fa7')
    assert len(wire) == PDU_ADV_CONNECT_DATA_SIZE
    assert parameters.encode() == wire
    assert Parameters.decode(wire) == parameters


@pytest.mark.parametrize('length', [0, 21, 23])
def test_connect_ind_rejects_truncated_or_extra_data(length):
    """CONNECT_IND decoding requires exactly 22 octets.

    Purpose: Verify ``Parameters.decode`` rejects LLData that is shorter or
    longer than the fixed CONNECT_IND size of 22 octets (Vol 6, Part B,
    2.3.3.1).

    Steps:
        1. For each parametrized length (0, 21, 23), decode a zero-filled
           buffer of that length.

    Expected:
        - ``ValueError`` mentioning '22 octets' is raised in every case.
    """
    with pytest.raises(ValueError, match='22 octets'):
        Parameters.decode(bytes(length))


@pytest.mark.parametrize(
    "field,value",
    [
        ("interval", LL_CONN_INTERVAL_MIN - 1),
        ("interval", LL_CONN_INTERVAL_MAX + 1),
        ("latency", LL_CONN_LATENCY_MAX + 1),
        ("timeout", LL_SUPERVISION_TIMEOUT_MIN - 1),
        ("timeout", LL_SUPERVISION_TIMEOUT_MAX + 1),
        ("latency", 20),
        ("window_size", LL_CONN_WINDOW_SIZE_MIN - 1),
        ("window_size", LL_CONN_WINDOW_SIZE_MAX + 1),
        ("window_offset", PARAMETERS.interval + 1),
        ("hop", LL_HOP_INCREMENT_MIN - 1),
        ("hop", LL_HOP_INCREMENT_MAX + 1),
        ("channel_map", 1),
        ("channel_map", 1 << LL_DATA_CHANNEL_COUNT | 3),
        ("access_address", 0),
        ("access_address", 0xFFFFFFFF),
        ("access_address", PDU_ADV_ACCESS_ADDRESS),
    ],
)
def test_invalid_connection_parameters(field, value):
    """Decoding rejects a CONNECT_IND with any out-of-range field.

    Purpose: Verify ``Parameters.decode`` raises when any individual field is
    outside its allowed range after encoding, covering interval, latency,
    timeout, window size/offset, hop increment, channel map and the reserved
    Access Address values (Vol 6, Part B, 2.3.3.1, 4.5.2).

    Steps:
        1. Replace one field of the fixed vector with an invalid value, encode
           it, then decode the resulting wire bytes.

    Expected:
        - ``ValueError`` is raised for every parametrized (field, value) case,
          including the advertising Access Address and the all-ones value.
    """
    with pytest.raises(ValueError):
        Parameters.decode(replace(PARAMETERS, **{field: value}).encode())
