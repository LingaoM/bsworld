# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""LE air-interface packet format and CRC (Core 6.3, Vol 6, Part B, 2.1, 2.2 and 3.1.1).

These are the PHY-level packet fields shared by the Radio and the Link Layer.
The Radio layer owns them so that it never depends on the Link Layer.
"""

# Common bit-field conversion.
PHY_OCTET_BITS = 8

# Physical packet fields: Core Vol 6, Part B, 2.1. Sizes exclude other fields.
PDU_PREAMBLE_1M_SIZE = 1
PDU_PREAMBLE_2M_SIZE = 2
PDU_ACCESS_ADDRESS_SIZE = 4
PDU_HEADER_SIZE = 2
PDU_CRC_SIZE = 3
# Includes extended header; excludes LL header (Core Vol 6, Part B, 2.3).
PDU_ADV_EXT_PAYLOAD_SIZE_MAX = 255
# Fixed advertising-channel Access Address.
PDU_ADV_ACCESS_ADDRESS = 0x8E89BED6
# Fixed advertising-channel CRC initialization.
PDU_ADV_CRC_INIT = 0x555555
# Core Vol 6, Part B, 3.1.1: polynomial in the CRC engine's LSB-first form.
PDU_CRC_POLYNOMIAL_REFLECTED = 0xDA6000

# Channel indices 0..36 are general-purpose channels (Core Vol 6, Part B, 1.4.1).
LL_DATA_CHANNEL_COUNT = 37


def crc24(pdu: bytes, crc_init: int = PDU_ADV_CRC_INIT) -> bytes:
    """Core Vol 6, Part B, 3.1.1: 24-bit CRC over the PDU, LSB of each octet first."""
    state = int(f'{crc_init:0{PDU_CRC_SIZE * PHY_OCTET_BITS}b}'[::-1], 2)
    for byte in pdu:
        for bit in range(PHY_OCTET_BITS):
            feedback = (state & 1) ^ ((byte >> bit) & 1)
            state >>= 1
            if feedback:
                state ^= PDU_CRC_POLYNOMIAL_REFLECTED
    return state.to_bytes(PDU_CRC_SIZE, 'little')
