# Adapted for the independent BSController package.
# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""One HCI configuration and notification context shared by LE command groups."""

from typing import TYPE_CHECKING

from bscontroller import hci
from bscontroller.capabilities import CONTROLLER_SUPPORTED_PHY_MASK
from bscontroller.hci.events import LeControllerEvents
from bscontroller.linklayer import LL_DATA_CHANNEL_MAP_ALL
from bscontroller.linklayer.discovery import Scanning
from bscontroller.linklayer.link import RadioLink
from bscontroller.linklayer.timing import LL_DEFAULT_SCAN_INTERVAL_US
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
        self.scan_parameters = Scanning(
            controller.public_address,
            LL_DEFAULT_SCAN_INTERVAL_US,
            LL_DEFAULT_SCAN_INTERVAL_US,
        )
        self.filter_duplicates = False
        self.seen: set[tuple] = set()
        self.fragments: dict[tuple[int, str], bytes] = {}
        self.host_channel_map = LL_DATA_CHANNEL_MAP_ALL
        self.default_tx_phys = self.default_rx_phys = CONTROLLER_SUPPORTED_PHY_MASK
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
