# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

from types import SimpleNamespace

import pytest

from bscontroller import hci
from bscontroller.hci.backend import RadioBackend
from bscontroller.hci.controller import Controller
from bscontroller.linklayer.connection import Connection as RadioConnection
from tests.unit.helpers import PARAMETERS

ErrorCode = hci.HCI_ErrorCode

ADDRESS = hci.Address('F0:F1:F2:F3:F4:01', hci.AddressType.PUBLIC_DEVICE)

PEER = hci.Address('F0:F1:F2:F3:F4:02', hci.AddressType.PUBLIC_DEVICE)


def radio_backend():
    return RadioBackend(SimpleNamespace(now_us=0))


@pytest.mark.asyncio
async def test_radio_reset_clears_shared_connection_state():
    backend = radio_backend()
    controller = Controller('radio', backend=backend)
    controller.send_hci_packet = lambda packet: None
    controller.event_mask = controller.le_event_mask = (1 << 64) - 1
    connection = RadioConnection(backend.link, PARAMETERS, PEER, 0, 0)
    backend.link.connections[connection.handle] = connection
    connection.establish()
    controller.on_packet(bytes(hci.HCI_Reset_Command()))
    assert not controller.le_connections
    assert not backend.link.connections


@pytest.mark.asyncio
async def test_power_on_and_reset_restore_specified_defaults():
    """Vol 4, Part E, 7.3.1, 7.3.2, 7.8.1, 7.8.5 and 7.8.10 default values."""
    controller = Controller('radio', backend=radio_backend())
    controller.send_hci_packet = lambda packet: None

    def check():
        assert controller.event_mask == hci.HCI_EVENT_MASK_DEFAULT
        assert controller.le_event_mask == hci.HCI_LE_EVENT_MASK_DEFAULT
        advertiser = controller.le_legacy_advertiser
        assert advertiser.advertising_interval_min == advertiser.advertising_interval_max == 0x0800
        assert advertiser.advertising_channel_map == 0x07
        scan = controller.le_procedures.scan_parameters
        assert scan.interval_us == scan.window_us == 0x0010 * hci.HCI_LE_SCAN_INTERVAL_UNIT_US

    check()
    controller.on_packet(
        bytes(
            hci.HCI_LE_Set_Advertising_Parameters_Command(
                advertising_interval_min=0x20,
                advertising_interval_max=0x30,
                advertising_type=0,
                own_address_type=0,
                peer_address_type=0,
                peer_address=PEER,
                advertising_channel_map=0x01,
                advertising_filter_policy=0,
            )
        )
    )
    assert controller.le_legacy_advertiser.advertising_channel_map == 0x01
    controller.on_packet(bytes(hci.HCI_Reset_Command()))
    check()
