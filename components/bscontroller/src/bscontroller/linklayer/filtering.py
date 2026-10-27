# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Device-filtering values shared by LL procedures and HCI parameter decoding.

Core Vol 6, Part B, 4.3 defines the filter policies. Decision instruction
flags/fields come from Vol 4, Part E, 7.8.145. These definitions carry protocol
values only; they own no HCI, radio or role state.
"""

from bscontroller.serialization import SpecableEnum, SpecableFlag


class DecisionMode(SpecableEnum):
    IGNORE_DECISION_PDUS = 0b00
    ALL_PDUS = 0b01
    DECISION_PDUS_ONLY = 0b11


class ScanningFilterPolicy(SpecableEnum):
    ACCEPT_ALL = 0x00
    FILTER_ACCEPT_LIST = 0x01
    ACCEPT_ALL_DIRECTED_RPAS = 0x02
    FILTER_ACCEPT_LIST_AND_ALL_DIRECTED_RPAS = 0x03


SCANNING_DECISION_MODE_SHIFT = 2
LEGACY_SCANNING_FILTER_POLICIES = frozenset(ScanningFilterPolicy)
EXTENDED_SCANNING_FILTER_POLICIES = frozenset(
    int(base) | (int(mode) << SCANNING_DECISION_MODE_SHIFT)
    for base in ScanningFilterPolicy
    for mode in DecisionMode
)


def scanning_decision_mode(policy: int) -> DecisionMode:
    return DecisionMode(policy >> SCANNING_DECISION_MODE_SHIFT)


class InitiatorFilterPolicy(SpecableEnum):
    PEER_ADDRESS = 0x00
    FILTER_ACCEPT_LIST = 0x01
    DECISION_PDUS_ONLY = 0x02
    FILTER_ACCEPT_LIST_ALL_PDUS = 0x03
    FILTER_ACCEPT_LIST_NON_DECISION_PDUS = 0x04

    @property
    def decision_mode(self) -> DecisionMode:
        if self == self.DECISION_PDUS_ONLY:
            return DecisionMode.DECISION_PDUS_ONLY
        if self in (
            self.FILTER_ACCEPT_LIST_ALL_PDUS,
            self.FILTER_ACCEPT_LIST_NON_DECISION_PDUS,
        ):
            return DecisionMode.ALL_PDUS
        return DecisionMode.IGNORE_DECISION_PDUS

    @property
    def filters_non_decision_pdus(self) -> bool:
        return self in (
            self.FILTER_ACCEPT_LIST,
            self.FILTER_ACCEPT_LIST_ALL_PDUS,
            self.FILTER_ACCEPT_LIST_NON_DECISION_PDUS,
        )


LEGACY_INITIATOR_FILTER_POLICIES = frozenset(
    (InitiatorFilterPolicy.PEER_ADDRESS, InitiatorFilterPolicy.FILTER_ACCEPT_LIST)
)


class DecisionTestFlags(SpecableFlag):
    START_NEW_GROUP = 1 << 0
    PASS_IF_MATCH = 1 << 1
    PASS_IF_NOT_MATCH = 1 << 2
    PASS_IF_ABSENT = 1 << 3


class DecisionTestField(SpecableEnum):
    RESOLVABLE_TAG = 0
    ADV_MODE = 6
    RSSI = 7
    PATH_LOSS = 8
    ADV_ADDRESS = 9
    ARBITRARY_DATA_EXACT_LENGTH_1 = 17
    ARBITRARY_DATA_EXACT_LENGTH_2 = 18
    ARBITRARY_DATA_EXACT_LENGTH_3 = 19
    ARBITRARY_DATA_EXACT_LENGTH_4 = 20
    ARBITRARY_DATA_EXACT_LENGTH_5 = 21
    ARBITRARY_DATA_EXACT_LENGTH_6 = 22
    ARBITRARY_DATA_EXACT_LENGTH_7 = 23
    ARBITRARY_DATA_EXACT_LENGTH_8 = 24
    ARBITRARY_DATA_MIN_LENGTH_1 = 33
    ARBITRARY_DATA_MIN_LENGTH_2 = 34
    ARBITRARY_DATA_MIN_LENGTH_3 = 35
    ARBITRARY_DATA_MIN_LENGTH_4 = 36
    ARBITRARY_DATA_MIN_LENGTH_5 = 37
    ARBITRARY_DATA_MIN_LENGTH_6 = 38
    ARBITRARY_DATA_MIN_LENGTH_7 = 39
    ARBITRARY_DATA_MIN_LENGTH_8 = 40
    ARBITRARY_DATA_MAX_LENGTH_1 = 49
    ARBITRARY_DATA_MAX_LENGTH_2 = 50
    ARBITRARY_DATA_MAX_LENGTH_3 = 51
    ARBITRARY_DATA_MAX_LENGTH_4 = 52
    ARBITRARY_DATA_MAX_LENGTH_5 = 53
    ARBITRARY_DATA_MAX_LENGTH_6 = 54
    ARBITRARY_DATA_MAX_LENGTH_7 = 55
    ARBITRARY_DATA_MAX_LENGTH_8 = 56


class DecisionAddressCheck(SpecableEnum):
    FILTER_ACCEPT_LIST = 0
    FIRST_ADDRESS = 1
    EITHER_ADDRESS = 2


DECISION_TEST_COUNT_MAX = 8
DECISION_TEST_PARAMETERS_SIZE = 16
DECISION_ARBITRARY_DATA_SIZE_MAX = 8
DECISION_ARBITRARY_LENGTH_MASK = 0x0F
