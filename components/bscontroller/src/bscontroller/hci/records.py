# Adapted for the independent BSController package.
# Copyright 2021-2022 Google LLC
# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# -----------------------------------------------------------------------------
# Imports
# -----------------------------------------------------------------------------
"""HCI configuration records and views of live Link Layer state (Core 6.3, Vol 4, Part E)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from bscontroller import hci
from bscontroller.linklayer.discovery import Advertising

if TYPE_CHECKING:
    from bscontroller.hci.controller import Controller
    from bscontroller.linklayer.connection import Connection


class LegacyAdvertiser:
    def __init__(
        self,
        controller: Controller,
        advertising_interval_min: int = hci.HCI_LE_ADV_INTERVAL_DEFAULT,
        advertising_interval_max: int = hci.HCI_LE_ADV_INTERVAL_DEFAULT,
        advertising_type: int = 0,
        own_address_type: int = 0,
        peer_address_type: int = 0,
        peer_address: hci.Address = hci.Address.ANY,
        advertising_channel_map: int = hci.HCI_LE_ADV_CHANNEL_MAP_DEFAULT,
        advertising_filter_policy: int = 0,
        advertising_data: bytes = b'',
        scan_response_data: bytes = b'',
        enabled: bool = False,
    ):
        self.controller = controller
        self.advertising_interval_min = advertising_interval_min
        self.advertising_interval_max = advertising_interval_max
        self.advertising_type = advertising_type
        self.own_address_type = own_address_type
        self.peer_address_type = peer_address_type
        self.peer_address = peer_address
        self.advertising_channel_map = advertising_channel_map
        self.advertising_filter_policy = advertising_filter_policy
        self._advertising_data = advertising_data
        self._scan_response_data = scan_response_data
        self._enabled = enabled

    @property
    def _link_layer_state(self) -> Advertising | None:
        procedures = self.controller.le_procedures
        return procedures.link.advertisers.get(-1) if procedures else None

    @property
    def advertising_data(self) -> bytes:
        state = self._link_layer_state
        return bytes(state.data) if state is not None else self._advertising_data

    @property
    def scan_response_data(self) -> bytes:
        state = self._link_layer_state
        return bytes(state.scan_response) if state is not None else self._scan_response_data

    @property
    def enabled(self) -> bool:
        state = self._link_layer_state
        return state.enabled if state is not None else self._enabled

    @property
    def address(self) -> hci.Address:
        '''Address used in advertising PDU.'''
        if self.own_address_type == hci.Address.PUBLIC_DEVICE_ADDRESS:
            return self.controller.public_address
        else:
            return self.controller.random_address


class AdvertisingSet:
    """Read-only advertising view; updates go through LL service operations."""

    def __init__(
        self,
        controller: Controller,
        handle: int,
        parameters: (hci.HCI_LE_Set_Extended_Advertising_Parameters_Command | None) = None,
        data: bytearray | None = None,
        scan_response_data: bytearray | None = None,
        periodic_advertising_data: bytearray | None = None,
        enabled: bool = False,
        random_address: hci.Address | None = None,
    ):
        self.controller = controller
        self.handle = handle
        self.parameters = parameters
        self._data = data if data is not None else bytearray()
        self._scan_response_data = scan_response_data if scan_response_data is not None else bytearray()
        self._periodic_advertising_data = (
            periodic_advertising_data if periodic_advertising_data is not None else bytearray()
        )
        self._enabled = enabled
        self._random_address = random_address

    @property
    def _link_layer_state(self) -> Advertising | None:
        procedures = self.controller.le_procedures
        return procedures.link.advertisers.get(self.handle) if procedures else None

    @property
    def data(self) -> bytes:
        state = self._link_layer_state
        return bytes(state.data if state is not None else self._data)

    @property
    def scan_response_data(self) -> bytes:
        state = self._link_layer_state
        return bytes(state.scan_response if state is not None else self._scan_response_data)

    @property
    def periodic_advertising_data(self) -> bytes:
        state = self._link_layer_state
        return bytes(state.periodic_data if state is not None else self._periodic_advertising_data)

    @property
    def enabled(self) -> bool:
        state = self._link_layer_state
        return state.enabled if state is not None else self._enabled

    @property
    def random_address(self) -> hci.Address | None:
        state = self._link_layer_state
        return state.random_address if state is not None else self._random_address

    @property
    def address(self) -> hci.Address | None:
        '''Address used in advertising PDU.'''
        if not self.parameters:
            return None
        if self.parameters.own_address_type == hci.Address.PUBLIC_DEVICE_ADDRESS:
            return self.controller.public_address
        else:
            return self.random_address


class ConnectionRecord:
    """Read-only HCI identity lookup backed by one live LE ACL connection."""

    def __init__(self, controller: Controller, connection: Connection):
        self.controller = controller
        self._connection = connection

    @property
    def handle(self) -> int:
        return self._connection.handle

    @property
    def role(self) -> hci.Role:
        return hci.Role(self._connection.role)

    @property
    def self_address(self) -> hci.Address:
        return self._connection.self_address or self.controller.public_address

    @property
    def peer_address(self) -> hci.Address:
        return self._connection.peer

    def on_hci_acl_data_packet(self, packet: hci.HCI_AclDataPacket) -> None:
        self.controller.le_procedures.on_hci_acl_data_packet(packet)
