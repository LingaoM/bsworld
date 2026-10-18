# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Event masks, duplicate history and state completion without notification."""

import struct

import pytest

from bscontroller import hci
from bscontroller.linklayer import ControlOpcode, LlId
from bscontroller.linklayer.discovery import Scanning
from bscontroller.linklayer.state import AdvertisingProperties, AdvertisingReport

ErrorCode = hci.HCI_ErrorCode
Opcode = ControlOpcode

ADDRESS = hci.Address('F0:F1:F2:F3:F4:01', hci.Address.PUBLIC_DEVICE_ADDRESS)


def test_masked_version_completion_retains_cache_and_clears_request(connection):
    connection.report_created()
    listener = connection.link.listener
    controller = listener.controller
    controller.event_mask &= ~(1 << (hci.HCI_READ_REMOTE_VERSION_INFORMATION_COMPLETE_EVENT - 1))
    connection.controls.request_version()
    peer = (hci.HCI_VERSION_BLUETOOTH_CORE_5_0, 1, 2)
    connection.control(bytes([Opcode.LL_VERSION_IND]) + struct.pack('<BHH', *peer))
    assert connection.controls.peer_version == peer
    assert not connection.controls.version_request
    assert not any(
        isinstance(event, hci.HCI_Read_Remote_Version_Information_Complete_Event) for event in controller.events
    )


@pytest.mark.parametrize(
    'llid,boundary',
    [
        (LlId.START, hci.HCI_ACL_PB_FIRST_FLUSHABLE),
        (LlId.CONTINUATION, hci.HCI_ACL_PB_CONTINUATION),
    ],
)
def test_received_acl_uses_controller_to_host_packet_boundaries(connection, llid, boundary):
    connection.accept(bytes([llid, 3]) + b'abc', True)
    packet = next(
        event for event in connection.link.listener.controller.events if isinstance(event, hci.HCI_AclDataPacket)
    )
    assert packet.pb_flag == boundary
    assert packet.data == b'abc'


def test_advertisement_event_masks_and_duplicates(controller):
    controller.backend.link.scan = Scanning(ADDRESS, 30_000, 30_000)
    controller.le_procedures.extended_scan = True
    controller.le_procedures.filter_duplicates = True
    controller.le_procedures.on_advertisement(
        ADDRESS, b'data', -45, AdvertisingReport(AdvertisingProperties.LEGACY_ADVERTISING_PDU_USED), None, 0, None
    )
    assert len(controller.events) == 1
    controller.le_procedures.on_advertisement(
        ADDRESS, b'data', -45, AdvertisingReport(AdvertisingProperties.LEGACY_ADVERTISING_PDU_USED), None, 0, None
    )
    assert len(controller.events) == 1
    controller.le_procedures.seen.clear()
    controller.le_event_mask = 0
    controller.le_procedures.on_advertisement(
        ADDRESS, b'data', -45, AdvertisingReport(AdvertisingProperties.LEGACY_ADVERTISING_PDU_USED), None, 0, None
    )
    assert len(controller.events) == 1


@pytest.mark.parametrize('enabled', [False, True])
@pytest.mark.parametrize(
    'event,field,bit',
    [
        (hci.HCI_LE_Scan_Timeout_Event(), 'event_mask', hci.HCI_LE_META_EVENT - 1),
        (
            hci.HCI_LE_Scan_Timeout_Event(),
            'le_event_mask',
            hci.HCI_LE_SCAN_TIMEOUT_EVENT - 1,
        ),
        (
            hci.HCI_Disconnection_Complete_Event(0, 1, hci.HCI_ErrorCode.REMOTE_USER_TERMINATED_CONNECTION_ERROR),
            'event_mask',
            hci.HCI_DISCONNECTION_COMPLETE_EVENT - 1,
        ),
        (
            hci.HCI_Encryption_Change_Event(0, 1, hci.HCI_Encryption_Change_Event.Enabled.E0_OR_AES_CCM),
            'event_mask',
            hci.HCI_ENCRYPTION_CHANGE_EVENT - 1,
        ),
        (
            hci.HCI_Encryption_Key_Refresh_Complete_Event(0, 1),
            'event_mask',
            hci.HCI_ENCRYPTION_KEY_REFRESH_COMPLETE_EVENT - 1,
        ),
        (
            hci.HCI_Authenticated_Payload_Timeout_Expired_Event(1),
            'event_mask_page_2',
            hci.HCI_AUTHENTICATED_PAYLOAD_TIMEOUT_EXPIRED_EVENT - hci.HCI_EVENT_MASK_PAGE_2_CODE_BASE,
        ),
    ],
)
def test_radio_event_delivery_uses_the_owning_mask(controller, event, field, bit, enabled):
    controller.event_mask_page_2 = (1 << 64) - 1
    setattr(controller, field, (1 << bit) if enabled else 0)
    controller.le_procedures._emit_hci_packet(event)
    assert controller.events == ([event] if enabled else [])


def test_radio_acl_credits_are_not_optional_events(controller):
    controller.event_mask = controller.le_event_mask = controller.event_mask_page_2 = 0
    event = hci.HCI_Number_Of_Completed_Packets_Event([1], [1])
    controller.le_procedures._emit_hci_packet(event)
    assert controller.events == [event]


@pytest.mark.asyncio
async def test_masked_advertising_completion_still_updates_public_state(controller):
    from bscontroller_tests.unit.helpers import extended_parameters

    controller.event_mask = controller.le_event_mask = 0
    commands = controller.le_procedures
    assert (
        commands.on_hci_le_set_extended_advertising_parameters_command(
            extended_parameters(advertising_event_properties=16)
        ).status
        == ErrorCode.SUCCESS
    )
    assert (
        commands.on_hci_le_set_extended_advertising_enable_command(
            hci.HCI_LE_Set_Extended_Advertising_Enable_Command(1, [0], [0], [1])
        ).status
        == ErrorCode.SUCCESS
    )
    assert controller.is_advertising
    await controller.backend.link.advance_to_us(2000)
    assert not controller.is_advertising
    assert not controller.advertising_sets[0].enabled
    assert controller.backend.link.radio.sent
    assert not controller.events
