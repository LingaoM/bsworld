# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Atomic decision programs for primary advertising reception.

Core Vol 4, Part E, 7.8.145 specifies OR between groups, AND within a group,
and separate flag results for matching, nonmatching and absent fields. Keep
the program immutable so a Host update cannot alter an in-flight evaluation.
"""

from dataclasses import dataclass

from bscontroller.address import RPA_HASH_SIZE, Address, AddressType
from bscontroller.errors import ErrorCode
from bscontroller.linklayer.filtering import (
    DECISION_ARBITRARY_DATA_SIZE_MAX,
    DECISION_ARBITRARY_LENGTH_MASK,
    DECISION_TEST_COUNT_MAX,
    DECISION_TEST_PARAMETERS_SIZE,
    DecisionAddressCheck,
    DecisionTestField,
    DecisionTestFlags,
)
from bscontroller.linklayer.pdu import (
    PDU_ADV_ADDRESS_SIZE,
    PDU_ADV_DECISION_DATA_SIZE_MAX,
    PDU_ADV_DECISION_RESOLVABLE_TAG_MASK,
    PDU_ADV_DECISION_RESOLVABLE_TAG_SIZE,
)
from bscontroller.linklayer.privacy import address_hash

DECISION_FIRST_ADDRESS_TYPE_OFFSET = 1
DECISION_FIRST_ADDRESS_OFFSET = DECISION_FIRST_ADDRESS_TYPE_OFFSET + 1
DECISION_SECOND_ADDRESS_TYPE_OFFSET = (
    DECISION_FIRST_ADDRESS_OFFSET + PDU_ADV_ADDRESS_SIZE
)
DECISION_SECOND_ADDRESS_OFFSET = DECISION_SECOND_ADDRESS_TYPE_OFFSET + 1
DECISION_SECOND_ADDRESS_END = DECISION_SECOND_ADDRESS_OFFSET + PDU_ADV_ADDRESS_SIZE


@dataclass(frozen=True)
class DecisionTest:
    flags: int
    field: int
    parameters: bytes


class DecisionProgram:
    def __init__(self, link):
        self.link = link
        self.tests: tuple[DecisionTest, ...] = ()

    def configure(self, flags, fields, parameters) -> int:
        if not flags or not flags[0] & DecisionTestFlags.START_NEW_GROUP:
            return ErrorCode.INVALID_COMMAND_PARAMETERS_ERROR
        if len(flags) > DECISION_TEST_COUNT_MAX:
            return ErrorCode.LIMIT_REACHED_ERROR
        if (
            len(flags) != len(fields)
            or len(flags) != len(parameters)
            or any(len(value) != DECISION_TEST_PARAMETERS_SIZE for value in parameters)
        ):
            return ErrorCode.INVALID_COMMAND_PARAMETERS_ERROR
        valid = frozenset(DecisionTestField)
        if any(field not in valid for field in fields):
            return ErrorCode.UNSUPPORTED_FEATURE_OR_PARAMETER_VALUE_ERROR
        self.tests = tuple(
            DecisionTest(flag, field, bytes(value))
            for flag, field, value in zip(flags, fields, parameters)
        )
        return ErrorCode.SUCCESS

    def accepts(self, pdu, rssi) -> bool:
        """Apply one committed program; no instructions means reject decisions."""
        if not self.tests or len(pdu.data) > PDU_ADV_DECISION_DATA_SIZE_MAX:
            return False
        flags, data = pdu.decision_flags, pdu.data
        if (
            flags & PDU_ADV_DECISION_RESOLVABLE_TAG_MASK
            and len(data) < PDU_ADV_DECISION_RESOLVABLE_TAG_SIZE
        ):
            return False
        tag = (
            data[:PDU_ADV_DECISION_RESOLVABLE_TAG_SIZE]
            if flags & PDU_ADV_DECISION_RESOLVABLE_TAG_MASK
            else None
        )
        arbitrary = (
            data[PDU_ADV_DECISION_RESOLVABLE_TAG_SIZE:] if tag is not None else data
        )
        accepted = False
        group = True
        for test in self.tests:
            if test.flags & DecisionTestFlags.START_NEW_GROUP:
                accepted |= group if test is not self.tests[0] else False
                group = True
            present, matched = self._check(test, pdu, rssi, tag, arbitrary)
            group &= bool(
                test.flags
                & (
                    DecisionTestFlags.PASS_IF_MATCH
                    if matched
                    else DecisionTestFlags.PASS_IF_NOT_MATCH
                )
                if present
                else test.flags & DecisionTestFlags.PASS_IF_ABSENT
            )
        return accepted or group

    def _check(self, test, pdu, rssi, tag, arbitrary):
        field, parameters = test.field, test.parameters
        if field == DecisionTestField.RESOLVABLE_TAG:
            return tag is not None, bool(
                tag is not None
                and address_hash(parameters, tag[RPA_HASH_SIZE:]) == tag[:RPA_HASH_SIZE]
            )
        if field == DecisionTestField.ADV_MODE:
            return True, bool(parameters[0] & (1 << pdu.mode))
        if field == DecisionTestField.RSSI:
            low, high = (
                int.from_bytes(bytes([value]), 'little', signed=True)
                for value in parameters[:2]
            )
            return rssi is not None, rssi is not None and low <= rssi <= high
        if field == DecisionTestField.PATH_LOSS:
            present = rssi is not None and pdu.tx_power is not None
            return present, bool(
                present and parameters[0] <= pdu.tx_power - rssi <= parameters[1]
            )
        if field == DecisionTestField.ADV_ADDRESS:
            if pdu.address is None:
                return False, False
            address = self.link.privacy.identity(
                Address(pdu.address, AddressType(pdu.random_address))
            )
            if address is None:
                return True, False
            if parameters[0] == DecisionAddressCheck.FILTER_ACCEPT_LIST:
                return True, address in self.link.accept_list
            addresses = [
                Address(
                    parameters[
                        DECISION_FIRST_ADDRESS_OFFSET:DECISION_SECOND_ADDRESS_TYPE_OFFSET
                    ],
                    AddressType(parameters[DECISION_FIRST_ADDRESS_TYPE_OFFSET]),
                )
            ]
            if parameters[0] == DecisionAddressCheck.EITHER_ADDRESS:
                addresses.append(
                    Address(
                        parameters[
                            DECISION_SECOND_ADDRESS_OFFSET:DECISION_SECOND_ADDRESS_END
                        ],
                        AddressType(parameters[DECISION_SECOND_ADDRESS_TYPE_OFFSET]),
                    )
                )
            return True, address in addresses
        length = field & DECISION_ARBITRARY_LENGTH_MASK
        present = bool(arbitrary) and (
            len(arbitrary) == length
            if field <= DecisionTestField.ARBITRARY_DATA_EXACT_LENGTH_8
            else len(arbitrary) >= length
            if field <= DecisionTestField.ARBITRARY_DATA_MIN_LENGTH_8
            else len(arbitrary) <= length
        )
        padded = arbitrary.ljust(DECISION_ARBITRARY_DATA_SIZE_MAX, b'\0')
        return present, all(
            value & mask == target
            for value, mask, target in zip(
                padded,
                parameters[:DECISION_ARBITRARY_DATA_SIZE_MAX],
                parameters[DECISION_ARBITRARY_DATA_SIZE_MAX:],
            )
        )
