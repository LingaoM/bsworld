# Adapted for the independent BSController package.
# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""One HCI configuration and notification context shared by LE command groups."""

from dataclasses import replace
from typing import TYPE_CHECKING

from bscontroller import hci
from bscontroller.hci import (
    HCI_LE_SCAN_INTERVAL_DEFAULT,
    HCI_LE_SCAN_INTERVAL_UNIT_US,
    HCI_LE_SCAN_WINDOW_DEFAULT,
)
from bscontroller.hci.events import LeControllerEvents
from bscontroller.linklayer.link import RadioLink
from bscontroller.linklayer.service import LinkLayerService
from bscontroller.radio.base import Radio

if TYPE_CHECKING:
    from bscontroller.hci.controller import Controller


SUCCESS = hci.HCI_ErrorCode.SUCCESS
INVALID = hci.HCI_ErrorCode.INVALID_COMMAND_PARAMETERS_ERROR
DISALLOWED = hci.HCI_ErrorCode.COMMAND_DISALLOWED_ERROR
UNSUPPORTED = hci.HCI_ErrorCode.UNSUPPORTED_FEATURE_OR_PARAMETER_VALUE_ERROR
UNKNOWN_ADV = hci.HCI_ErrorCode.UNKNOWN_ADVERTISING_IDENTIFIER_ERROR


class LeControllerContext(LeControllerEvents):
    """The public Controller owns HCI configuration; RadioLink owns active RF."""

    def __init__(self, controller: 'Controller', radio: Radio):
        self.controller = controller
        self.link = RadioLink(
            radio,
            self,
            int(controller.le_features),
            seed=int.from_bytes(bytes(controller.public_address), 'little'),
        )
        self.extended_scan = False
        self.ll = LinkLayerService(
            self.link,
            controller.public_address,
            HCI_LE_SCAN_INTERVAL_DEFAULT * HCI_LE_SCAN_INTERVAL_UNIT_US,
            HCI_LE_SCAN_WINDOW_DEFAULT * HCI_LE_SCAN_INTERVAL_UNIT_US,
        )
        self.filter_duplicates = False
        self.seen: set[tuple] = set()
        self.fragments: dict[tuple[int, str], bytes] = {}
        self.period_duplicate_reset = False
        self.extended_commands: bool | None = None

    @property
    def now_us(self) -> int:
        return self.link.now_us

    def _address(self, own_address_type: int):
        return (
            self.controller.random_address
            if own_address_type == hci.OwnAddressType.RANDOM
            else self.controller.public_address
        )

    @property
    def scan_parameters(self):
        return replace(
            self.ll.scan_parameters,
            backoff=replace(self.ll.scan_parameters.backoff),
            windows=tuple(
                replace(window) for window in self.ll.scan_parameters.windows
            ),
        )

    @property
    def host_channel_map(self):
        return self.ll.host_channel_map

    @property
    def default_tx_phys(self):
        return self.ll.default_tx_phys

    @property
    def default_rx_phys(self):
        return self.ll.default_rx_phys
