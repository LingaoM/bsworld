# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Independent LL.TS.p28 Tables 4.2-89/90 decision-field test vectors."""

from dataclasses import dataclass

from bscontroller import hci
from tests.qualification.privacy import (
    FALLBACK,
    LOCAL_IRK,
    PEER_IRK,
    private_address,
)
from tests.qualification.tester import LOWER_PERIPHERAL_PUBLIC_ADDRESS, PEER_ADDRESS

TAG_KEY = bytes.fromhex('001102330455067708990abb0cdd0eff')[::-1]


@dataclass(frozen=True)
class DecisionVector:
    number: int
    field: int
    parameters: bytes
    data: bytes = b'\0'
    mode: int = 0
    address: hci.Address | None = None
    result: str = 'P'


def address_parameters(
    check, first=LOWER_PERIPHERAL_PUBLIC_ADDRESS, second=PEER_ADDRESS
):
    return (
        bytes([check, first.address_type])
        + bytes(first)
        + bytes([second.address_type])
        + bytes(second)
        + b'\0'
    )


def flag_vectors():
    """All 62 outer rounds, including the table's field-absence outcomes."""
    tag = bytes(private_address(TAG_KEY))
    vectors = [
        DecisionVector(1, 0, TAG_KEY, b'\1' + tag),
        DecisionVector(
            2,
            0,
            bytes.fromhex('deadbeaf3045506708990abb0cdd0eff')[::-1],
            b'\1' + tag,
            result='F',
        ),
        DecisionVector(3, 0, TAG_KEY, b'\0' + tag, result='A'),
    ]
    parameters = bytes.fromhex('fffff000000000004a4b400000000000')
    for index, field in enumerate((19, 20, 21, 35, 36, 37, 51, 52, 53)):
        present = field in (20, 35, 36, 52, 53)
        for passing in (False, True):
            vectors.append(
                DecisionVector(
                    4 + index * 2 + int(passing),
                    field,
                    parameters,
                    b'\0' + (b'JKL' + b'M' if passing else b'JKP\0'),
                    result=('P' if passing else 'F') if present else 'A',
                )
            )
    for number, mode, mask in (
        [(22 + mask, 0, mask) for mask in range(8)]
        + [(30 + index, 1, mask) for index, mask in enumerate((1, 2, 4, 6))]
        + [(34 + index, 2, mask) for index, mask in enumerate((1, 2, 4, 6))]
    ):
        vectors.append(
            DecisionVector(
                number,
                6,
                bytes([mask]) + bytes(15),
                mode=mode,
                result='P' if mask & (1 << mode) else 'F',
            )
        )
    for base, rpa in ((38, False), (51, True)):
        for index, identity in enumerate(
            (LOWER_PERIPHERAL_PUBLIC_ADDRESS, PEER_ADDRESS)
        ):
            parameters = [
                address_parameters(0),
                address_parameters(1),
                address_parameters(1, PEER_ADDRESS),
                address_parameters(2),
                address_parameters(2, second=FALLBACK),
                address_parameters(2, FALLBACK, PEER_ADDRESS),
            ]
            outcomes = (
                ('F', 'P', 'F', 'P', 'P', 'F')
                if index == 0
                else ('P', 'F', 'P', 'P', 'F', 'P')
            )
            address = (
                private_address(PEER_IRK if index == 0 else LOCAL_IRK)
                if rpa
                else identity
            )
            for offset, (params, outcome) in enumerate(zip(parameters, outcomes)):
                vectors.append(
                    DecisionVector(
                        base + index * 6 + offset,
                        9,
                        params,
                        address=address,
                        result=outcome,
                    )
                )
    vectors.append(DecisionVector(50, 9, address_parameters(2), result='A'))
    return sorted(vectors, key=lambda vector: vector.number)
