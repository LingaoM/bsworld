# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""CRC/CSA vectors, reproducible Access Addresses and RF switching arithmetic."""

import pytest

from bscontroller.linklayer import (
    PDU_ADV_EXT_PAYLOAD_SIZE_MAX,
    PDU_HEADER_SIZE,
)
from bscontroller.radio.base import (
    PHY_CODED_S2_FACTOR,
    PHY_CODED_S8_FACTOR,
    Phy,
    RadioSwitch,
)


@pytest.mark.parametrize(
    'phy,coding,duration',
    [
        (Phy.LE_1M, PHY_CODED_S8_FACTOR, 80),
        (Phy.LE_2M, PHY_CODED_S8_FACTOR, 44),
        (Phy.LE_CODED, PHY_CODED_S2_FACTOR, 462),
        (Phy.LE_CODED, PHY_CODED_S8_FACTOR, 720),
    ],
)
def test_empty_data_pdu_airtime(phy, coding, duration):
    """Air time of a header-only PDU matches each PHY and coding.

    Purpose: Verify ``Phy.airtime_us`` returns the on-air duration of an empty
    (header-only) Data PDU for 1M, 2M and Coded PHYs, including the S=2 and S=8
    coding factors (Core Vol 6, Part B, 2.1, 2.2).

    Steps:
        1. For each parametrized (PHY, coding) pair, compute
           ``airtime_us(PDU_HEADER_SIZE, coding)``.

    Expected:
        - The duration equals the expected microseconds: 80 (1M), 44 (2M),
          462 (Coded S=2) and 720 (Coded S=8).
    """
    assert Phy(phy).airtime_us(PDU_HEADER_SIZE, coding) == duration


@pytest.mark.parametrize(
    'size',
    [-1, 0, PDU_HEADER_SIZE - 1, PDU_HEADER_SIZE + PDU_ADV_EXT_PAYLOAD_SIZE_MAX + 1],
)
def test_invalid_airtime_size(size):
    """Air time rejects sizes below the header or above the maximum payload.

    Purpose: Verify ``Phy.airtime_us`` raises for PDU sizes that cannot occur
    on air: negative, zero, shorter than the header, or longer than the
    extended-payload maximum.

    Steps:
        1. For each parametrized out-of-range size, call
           ``Phy.LE_1M.airtime_us``.

    Expected:
        - ``ValueError`` is raised for every size.
    """
    with pytest.raises(ValueError):
        Phy.LE_1M.airtime_us(size)


@pytest.mark.parametrize(
    'now,channel,phy,transmit,expected',
    [
        (99, 37, Phy.LE_1M, True, 100),
        (149, 37, Phy.LE_1M, True, 150),
        (99, 38, Phy.LE_1M, True, 150),
        (124, 38, Phy.LE_1M, True, 150),
        (249, 38, Phy.LE_1M, True, 250),
        (99, 37, Phy.LE_CODED, True, 150),
        (99, 37, Phy.LE_1M, False, 150),
        (149, 37, Phy.LE_1M, False, 150),
    ],
)
def test_radio_switching_uses_idle_time(now, channel, phy, transmit, expected):
    """Earliest start reuses idle time toward the mandatory switch gap.

    Purpose: Verify ``RadioSwitch.earliest_start_us`` counts time already spent
    idle since the previous operation against the switch time, so a retune to a
    different channel, PHY or direction cannot begin before the radio is ready
    (Core Vol 6, Part B, 4.2.1 inter-frame and switching timing).

    Steps:
        1. Build a switch with a 50 us switch time and complete a 1M transmit
           on channel 37 ending at 100 us.
        2. For each parametrized (now, channel, phy, transmit), ask for the
           earliest start.

    Expected:
        - The earliest start equals the expected value: no delay once enough
          idle time has elapsed, otherwise pushed to the end of the switch gap,
          and a PHY or direction change forces the full gap.
    """
    switch = RadioSwitch(switch_time_us=50)
    switch.complete(37, Phy.LE_1M, transmit=True, end_us=100)
    assert switch.earliest_start_us(now, channel, phy, transmit=transmit) == expected


def test_first_radio_operation_does_not_require_switching():
    """The very first radio operation starts without a switch gap.

    Purpose: Verify ``RadioSwitch.earliest_start_us`` on a fresh switch (no
    previous operation) allows the first operation to begin immediately, at the
    next microsecond.

    Steps:
        1. Ask a fresh ``RadioSwitch`` for the earliest 1M transmit start on
           channel 37 at time 0.

    Expected:
        - The earliest start is 1 (the next microsecond), with no switch gap.
    """
    assert RadioSwitch().earliest_start_us(0, 37, Phy.LE_1M, transmit=True) == 1


def test_zero_switch_time_allows_raw_tester_to_retune_immediately():
    """A zero switch time lets the radio retune with no gap.

    Purpose: Verify a ``RadioSwitch`` configured with zero switch time (a raw
    tester) can start the next operation immediately after the previous one
    ends, even across a channel/PHY/direction change.

    Steps:
        1. Build a switch with switch time 0 and complete a 1M transmit on
           channel 37 ending at 100 us.
        2. Ask for the earliest Coded receive start on channel 38 at time 99.
        3. Ask again at time 200.

    Expected:
        - At time 99 the earliest start is 100 (the previous end), with no gap.
        - At time 200 it is 201 (the next microsecond).
    """
    switch = RadioSwitch(switch_time_us=0)
    switch.complete(37, Phy.LE_1M, transmit=True, end_us=100)
    assert switch.earliest_start_us(99, 38, Phy.LE_CODED, transmit=False) == 100
    assert switch.earliest_start_us(200, 38, Phy.LE_CODED, transmit=False) == 201
