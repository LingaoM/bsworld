# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Live public state views and connection publication indexes."""

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
async def test_radio_connections_use_shared_handles_and_hci_acl_lookup():
    backend = radio_backend()
    controller = Controller('radio', backend=backend, public_address=ADDRESS)
    packets = []
    controller.send_hci_packet = packets.append
    controller.event_mask = controller.le_event_mask = (1 << 64) - 1
    occupied_peer = hci.Address('F0:F1:F2:F3:F4:03', 0)
    occupied = RadioConnection(
        backend.link,
        PARAMETERS,
        occupied_peer,
        hci.Role.CENTRAL,
        0,
        self_address=ADDRESS,
    )
    backend.link.connections[occupied.handle] = occupied
    occupied.report_created()
    connection = RadioConnection(
        backend.link,
        PARAMETERS,
        PEER,
        hci.Role.CENTRAL,
        0,
        self_address=ADDRESS,
    )
    backend.link.connections[connection.handle] = connection
    assert connection.handle == 2
    assert controller.find_connection_by_handle(2) is None
    connection.establish()
    record = controller.find_connection_by_handle(2)
    assert record is not None
    assert record.peer_address == PEER and record.self_address == ADDRESS
    controller.on_packet(
        bytes(
            hci.HCI_AclDataPacket(
                connection_handle=2,
                pb_flag=hci.HCI_ACL_PB_FIRST_FLUSHABLE,
                bc_flag=0,
                data_total_length=3,
                data=b'abc',
            )
        )
    )
    assert connection.event.queue[-1].payload == b'abc'
    connection.complete(ErrorCode.REMOTE_USER_TERMINATED_CONNECTION_ERROR)
    assert controller.find_connection_by_handle(2) is None
    assert controller.find_connection_by_handle(1) is not None
    assert packets[-1].connection_handle == 2


def test_public_connection_record_tracks_the_live_identity(connection):
    connection.report_created()
    controller = connection.link.listener.sink.controller
    record = controller.find_connection_by_handle(connection.handle)
    assert record is not None
    updated = hci.Address('C0:12:34:56:78:9A')
    connection.self_address = updated
    assert record.self_address == updated
    with pytest.raises(AttributeError):
        record.self_address = controller.public_address
    assert connection.self_address == updated


@pytest.mark.parametrize('same_peer', [False, True])
def test_retained_connection_record_does_not_follow_a_reused_handle(
    connection, same_peer
):
    connection.report_created()
    controller = connection.link.listener.sink.controller
    old_record = controller.find_connection_by_handle(connection.handle)
    old_peer, old_role = connection.peer, connection.role
    final_address = hci.Address('C0:12:34:56:78:9A')
    connection.self_address = final_address
    connection.complete(ErrorCode.REMOTE_USER_TERMINATED_CONNECTION_ERROR)

    new_peer = old_peer if same_peer else hci.Address('F0:F1:F2:F3:F4:99')
    replacement = RadioConnection(
        connection.link,
        PARAMETERS,
        new_peer,
        hci.Role.CENTRAL,
        0,
        self_address=ADDRESS,
    )
    connection.link.connections[replacement.handle] = replacement
    replacement.report_created()
    assert replacement.handle == connection.handle
    assert controller.find_connection_by_handle(replacement.handle) is not old_record
    assert old_record.peer_address == old_peer
    assert old_record.role == old_role
    assert old_record.self_address == final_address


def test_public_advertising_data_is_an_immutable_view(controller):
    from tests.unit.helpers import extended_parameters

    commands = controller.le_procedures
    parameters = extended_parameters(advertising_event_properties=16)
    assert (
        commands.on_hci_le_set_extended_advertising_parameters_command(
            parameters
        ).status
        == ErrorCode.SUCCESS
    )
    record = controller.advertising_sets[0]
    service = commands.ll.advertising
    service.store_data(0, 'data', b'advertising data')
    service.store_data(0, 'scan_response', b'scan response')
    service.store_data(0, 'periodic_data', b'periodic data')
    snapshot = record.data
    assert isinstance(snapshot, bytes)
    with pytest.raises(AttributeError):
        record.data = b'bypass LL'
    assert (
        commands.on_hci_le_set_extended_advertising_parameters_command(
            parameters
        ).status
        == ErrorCode.SUCCESS
    )
    assert record.data == b'advertising data'
    assert record.scan_response_data == b'scan response'
    assert record.periodic_advertising_data == b'periodic data'
    service.store_data(0, 'data', b'new data')
    assert record.data == b'new data' and snapshot == b'advertising data'
