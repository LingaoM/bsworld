# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

import random

import pytest

from bscontroller.linklayer.bitstream import crc24, generate_access_address
from tests.unit.helpers import check_access_address


def test_access_address_generation_is_reproducible_and_valid_on_coded():
    generator = random.Random(17)
    used = set()
    values = []
    for _ in range(1000):
        value = generate_access_address(generator, used)
        check_access_address(value)
        used.add(value)
        values.append(value)
    again = random.Random(17)
    assert values == [generate_access_address(again, set()) for _ in values]


@pytest.mark.parametrize(
    'pdu,expected',
    [
        (b'', 'aaaaaa'),
        (b'123456789', '565ac2'),
        (bytes(range(39)), '1d0e9b'),
        (
            bytes.fromhex('021c01f4f3f2f1f00201041209507974686f6e2d526164696f2d44656d6f'),
            '9f800b',
        ),
    ],
)
def test_crc_against_independent_radio_model(pdu, expected):
    assert crc24(pdu).hex() == expected
