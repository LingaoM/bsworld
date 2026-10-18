# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Live public state views and connection publication indexes."""

from types import SimpleNamespace

import pytest

from bscontroller import hci
from bscontroller.hci.backend import RadioBackend
from bscontroller.hci.controller import Controller
from bscontroller.hci.records import ConnectionRecord
from bscontroller.linklayer.connection import Connection as RadioConnection
from bscontroller_tests.unit.helpers import PARAMETERS

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
    controller.le_connections[occupied_peer] = ConnectionRecord(
        controller, SimpleNamespace(handle=1, role=hci.Role.CENTRAL, self_address=ADDRESS, peer=occupied_peer)
    )
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
    assert controller.find_le_connection_by_handle(2) is None
    connection.establish()
    record = controller.find_le_connection_by_handle(2)
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
    assert connection.queue[-1].payload == b'abc'
    connection.complete(ErrorCode.REMOTE_USER_TERMINATED_CONNECTION_ERROR)
    assert controller.find_le_connection_by_handle(2) is None
    assert controller.find_le_connection_by_handle(1) is not None
    assert packets[-1].connection_handle == 2


def test_public_connection_record_tracks_the_live_identity(connection):
    connection.report_created()
    controller = connection.link.listener.controller
    record = controller.find_le_connection_by_handle(connection.handle)
    assert record is not None
    updated = hci.Address('C0:12:34:56:78:9A')
    connection.self_address = updated
    assert record.self_address == updated
    record.self_address = controller.public_address
    assert connection.self_address == controller.public_address


def test_public_advertising_buffers_survive_reconfiguration(controller):
    from bscontroller_tests.unit.helpers import extended_parameters

    commands = controller.le_procedures
    parameters = extended_parameters(advertising_event_properties=16)
    assert commands.on_hci_le_set_extended_advertising_parameters_command(parameters).status == ErrorCode.SUCCESS
    record = controller.advertising_sets[0]
    data, response = record.data, record.scan_response_data
    periodic = record.periodic_advertising_data
    data.extend(b'advertising data')
    response.extend(b'scan response')
    periodic.extend(b'periodic data')
    assert commands.on_hci_le_set_extended_advertising_parameters_command(parameters).status == ErrorCode.SUCCESS
    runtime = controller.backend.link.advertisers[0]
    assert record.data is runtime.data is data
    assert record.scan_response_data is runtime.scan_response is response
    assert record.periodic_advertising_data is runtime.periodic_data is periodic
    assert data == b'advertising data' and response == b'scan response'
    assert periodic == b'periodic data'
