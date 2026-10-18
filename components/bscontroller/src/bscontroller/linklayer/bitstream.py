# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""LE CRC and Access Address generation (Core 6.3, Vol 6, Part B, 2.1.2/3.1.1)."""

from random import Random

from bscontroller.linklayer import (
    PDU_ACCESS_ADDRESS_CODED_LSB_BITS,
    PDU_ACCESS_ADDRESS_CODED_LSB_ONES_MIN,
    PDU_ACCESS_ADDRESS_CODED_TRANSITION_BITS,
    PDU_ACCESS_ADDRESS_CODED_TRANSITIONS_MAX,
    PDU_ACCESS_ADDRESS_CONSECUTIVE_BITS_MAX,
    PDU_ACCESS_ADDRESS_MSB_TRANSITIONS_MIN,
    PDU_ACCESS_ADDRESS_MSB_WINDOW_BITS,
    PDU_ACCESS_ADDRESS_SIZE,
    PDU_ACCESS_ADDRESS_TRANSITIONS_MAX,
    PDU_ADV_ACCESS_ADDRESS,
    PDU_ADV_CRC_INIT,
    PDU_CRC_POLYNOMIAL_REFLECTED,
    PDU_CRC_SIZE,
)
from bscontroller.radio.base import PHY_OCTET_BITS


def crc24(pdu: bytes, crc_init: int = PDU_ADV_CRC_INIT) -> bytes:
    state = int(f'{crc_init:0{PDU_CRC_SIZE * PHY_OCTET_BITS}b}'[::-1], 2)
    for byte in pdu:
        for bit in range(PHY_OCTET_BITS):
            feedback = (state & 1) ^ ((byte >> bit) & 1)
            state >>= 1
            if feedback:
                state ^= PDU_CRC_POLYNOMIAL_REFLECTED
    return state.to_bytes(PDU_CRC_SIZE, 'little')


def generate_access_address(generator: Random, used: set[int]) -> int:
    """Seeded data Access Address, valid for uncoded and Coded transmission."""
    width = PDU_ACCESS_ADDRESS_SIZE * PHY_OCTET_BITS
    while True:
        value = generator.getrandbits(width)
        if value in used or (value ^ PDU_ADV_ACCESS_ADDRESS).bit_count() <= 1:
            continue
        bits = f'{value:0{width}b}'
        run = PDU_ACCESS_ADDRESS_CONSECUTIVE_BITS_MAX + 1
        transitions = value ^ (value >> 1)
        msb = value >> (width - PDU_ACCESS_ADDRESS_MSB_WINDOW_BITS)
        if (
            '0' * run in bits
            or '1' * run in bits
            or len(set(value.to_bytes(PDU_ACCESS_ADDRESS_SIZE, 'little'))) == 1
            or (transitions & ((1 << (width - 1)) - 1)).bit_count() > PDU_ACCESS_ADDRESS_TRANSITIONS_MAX
            or ((msb ^ (msb >> 1)) & ((1 << (PDU_ACCESS_ADDRESS_MSB_WINDOW_BITS - 1)) - 1)).bit_count()
            < PDU_ACCESS_ADDRESS_MSB_TRANSITIONS_MIN
            or (value & ((1 << PDU_ACCESS_ADDRESS_CODED_LSB_BITS) - 1)).bit_count()
            < PDU_ACCESS_ADDRESS_CODED_LSB_ONES_MIN
            or (transitions & ((1 << (PDU_ACCESS_ADDRESS_CODED_TRANSITION_BITS - 1)) - 1)).bit_count()
            > PDU_ACCESS_ADDRESS_CODED_TRANSITIONS_MAX
        ):
            continue
        return value
