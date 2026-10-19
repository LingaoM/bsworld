# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""CRC/CSA vectors, reproducible Access Addresses and RF switching arithmetic."""

import pytest

from bscontroller.linklayer import (
    PDU_ADV_EXT_PAYLOAD_SIZE_MAX,
    PDU_HEADER_SIZE,
)
from bscontroller.radio.base import PHY_CODED_S2_FACTOR, PHY_CODED_S8_FACTOR, Phy, RadioSwitch


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
    assert Phy(phy).airtime_us(PDU_HEADER_SIZE, coding) == duration


@pytest.mark.parametrize(
    'size',
    [-1, 0, PDU_HEADER_SIZE - 1, PDU_HEADER_SIZE + PDU_ADV_EXT_PAYLOAD_SIZE_MAX + 1],
)
def test_invalid_airtime_size(size):
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
    switch = RadioSwitch(switch_time_us=50)
    switch.complete(37, Phy.LE_1M, transmit=True, end_us=100)
    assert switch.earliest_start_us(now, channel, phy, transmit=transmit) == expected


def test_first_radio_operation_does_not_require_switching():
    assert RadioSwitch().earliest_start_us(0, 37, Phy.LE_1M, transmit=True) == 1


def test_zero_switch_time_allows_raw_tester_to_retune_immediately():
    switch = RadioSwitch(switch_time_us=0)
    switch.complete(37, Phy.LE_1M, transmit=True, end_us=100)
    assert switch.earliest_start_us(99, 38, Phy.LE_CODED, transmit=False) == 100
    assert switch.earliest_start_us(200, 38, Phy.LE_CODED, transmit=False) == 201
