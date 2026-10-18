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
        advertising_interval_min: int = 0,
        advertising_interval_max: int = 0,
        advertising_type: int = 0,
        own_address_type: int = 0,
        peer_address_type: int = 0,
        peer_address: hci.Address = hci.Address.ANY,
        advertising_channel_map: int = 0,
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

    @advertising_data.setter
    def advertising_data(self, value: bytes) -> None:
        state = self._link_layer_state
        if state is None:
            self._advertising_data = value
        else:
            state.data = bytearray(value)

    @property
    def scan_response_data(self) -> bytes:
        state = self._link_layer_state
        return bytes(state.scan_response) if state is not None else self._scan_response_data

    @scan_response_data.setter
    def scan_response_data(self, value: bytes) -> None:
        state = self._link_layer_state
        if state is None:
            self._scan_response_data = value
        else:
            state.scan_response = bytearray(value)

    @property
    def enabled(self) -> bool:
        state = self._link_layer_state
        return state.enabled if state is not None else self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        state = self._link_layer_state
        if state is None:
            self._enabled = value
        else:
            state.enabled = value

    @property
    def address(self) -> hci.Address:
        '''Address used in advertising PDU.'''
        if self.own_address_type == hci.Address.PUBLIC_DEVICE_ADDRESS:
            return self.controller.public_address
        else:
            return self.controller.random_address


class AdvertisingSet:
    """Public advertising record, backed by its radio context when one exists."""

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
    def data(self) -> bytearray:
        state = self._link_layer_state
        return state.data if state is not None else self._data

    @data.setter
    def data(self, value: bytearray) -> None:
        state = self._link_layer_state
        if state is None:
            self._data = value
        else:
            state.data = value

    @property
    def scan_response_data(self) -> bytearray:
        state = self._link_layer_state
        return state.scan_response if state is not None else self._scan_response_data

    @scan_response_data.setter
    def scan_response_data(self, value: bytearray) -> None:
        state = self._link_layer_state
        if state is None:
            self._scan_response_data = value
        else:
            state.scan_response = value

    @property
    def periodic_advertising_data(self) -> bytearray:
        state = self._link_layer_state
        return state.periodic_data if state is not None else self._periodic_advertising_data

    @periodic_advertising_data.setter
    def periodic_advertising_data(self, value: bytearray) -> None:
        state = self._link_layer_state
        if state is None:
            self._periodic_advertising_data = value
        else:
            state.periodic_data = value

    @property
    def enabled(self) -> bool:
        state = self._link_layer_state
        return state.enabled if state is not None else self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        state = self._link_layer_state
        if state is None:
            self._enabled = value
        else:
            state.enabled = value

    @property
    def random_address(self) -> hci.Address | None:
        state = self._link_layer_state
        return state.random_address if state is not None else self._random_address

    @random_address.setter
    def random_address(self, value: hci.Address | None) -> None:
        state = self._link_layer_state
        if state is None:
            self._random_address = value
        else:
            state.random_address = value

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
    """HCI handle/address lookup backed by one live LE ACL connection."""

    def __init__(self, controller: Controller, connection: Connection):
        self.controller = controller
        self.connection = connection

    @property
    def handle(self) -> int:
        return self.connection.handle

    @handle.setter
    def handle(self, value: int) -> None:
        self.connection.handle = value

    @property
    def role(self) -> hci.Role:
        return hci.Role(self.connection.role)

    @role.setter
    def role(self, value: hci.Role) -> None:
        self.connection.role = value

    @property
    def self_address(self) -> hci.Address:
        return self.connection.self_address or self.controller.public_address

    @self_address.setter
    def self_address(self, value: hci.Address) -> None:
        self.connection.self_address = value

    @property
    def peer_address(self) -> hci.Address:
        return self.connection.peer

    @peer_address.setter
    def peer_address(self, value: hci.Address) -> None:
        self.connection.peer = value

    def on_hci_acl_data_packet(self, packet: hci.HCI_AclDataPacket) -> None:
        self.controller.le_procedures.on_hci_acl_data_packet(packet)
