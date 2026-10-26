# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

from types import SimpleNamespace

import pytest

from bscontroller import hci
from bscontroller.hci.backend import RadioBackend
from bscontroller.hci.controller import Controller

ErrorCode = hci.HCI_ErrorCode
# BR/EDR-only opcodes (Vol 4, Part E, 7.1.1, 7.1.5 and 7.4.4); this LE Controller has no codec for them.
INQUIRY_OPCODE = hci.hci_command_op_code(0x01, 0x0001)
CREATE_CONNECTION_OPCODE = hci.hci_command_op_code(0x01, 0x0005)
READ_LOCAL_EXTENDED_FEATURES_OPCODE = hci.hci_command_op_code(0x04, 0x0004)

ADDRESS = hci.Address('F0:F1:F2:F3:F4:01', hci.AddressType.PUBLIC_DEVICE)


def radio_backend():
    return RadioBackend(SimpleNamespace(now_us=0))


@pytest.mark.asyncio
async def test_controller_decodes_hci_and_builds_command_complete():
    controller = Controller('test', backend=radio_backend(), public_address=ADDRESS)
    packets = []
    controller.send_hci_packet = packets.append
    controller.on_packet(bytes(hci.HCI_Read_BD_ADDR_Command()))
    assert len(packets) == 1
    event = packets[0]
    assert isinstance(event, hci.HCI_Command_Complete_Event)
    assert event.command_opcode == hci.HCI_READ_BD_ADDR_COMMAND
    assert event.return_parameters.status == ErrorCode.SUCCESS
    assert event.return_parameters.bd_addr == ADDRESS


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'opcode,parameters',
    [
        (READ_LOCAL_EXTENDED_FEATURES_OPCODE, b''),
        (READ_LOCAL_EXTENDED_FEATURES_OPCODE, bytes(255)),
        (CREATE_CONNECTION_OPCODE, b'\xff'),
    ],
)
async def test_unsupported_command_is_rejected_before_parameter_decoding(opcode, parameters):
    controller = Controller('radio', backend=radio_backend())
    packets = []
    controller.send_hci_packet = packets.append
    controller.on_packet(bytes(hci.HCI_Command(parameters, op_code=opcode)))
    assert len(packets) == 1
    event = packets[0]
    assert event.command_opcode == opcode and event.num_hci_command_packets == 1
    if isinstance(event, hci.HCI_Command_Status_Event):
        assert event.status == ErrorCode.UNKNOWN_HCI_COMMAND_ERROR
    else:
        assert isinstance(event, hci.HCI_Command_Complete_Event)
        assert event.return_parameters.status == ErrorCode.UNKNOWN_HCI_COMMAND_ERROR


@pytest.mark.asyncio
async def test_unsupported_opcode_does_not_bypass_hci_frame_length_validation():
    from bscontroller.errors import InvalidPacketError

    controller = Controller('radio', backend=radio_backend())
    packets = []
    controller.send_hci_packet = packets.append
    packet = bytearray(bytes(hci.HCI_Command(b'', op_code=INQUIRY_OPCODE)))
    packet[3] = 1
    with pytest.raises(InvalidPacketError):
        controller.on_packet(packet)
    assert not packets


@pytest.mark.asyncio
async def test_radio_never_falls_back_to_local_encryption():
    controller = Controller('radio', backend=radio_backend())
    packets = []
    controller.send_hci_packet = packets.append
    controller.on_packet(
        bytes(
            hci.HCI_LE_Enable_Encryption_Command(
                connection_handle=1,
                random_number=bytes(8),
                encrypted_diversifier=0,
                long_term_key=bytes(16),
            )
        )
    )
    assert isinstance(packets[0], hci.HCI_Command_Status_Event)
    assert packets[0].status == ErrorCode.UNKNOWN_CONNECTION_IDENTIFIER_ERROR
    assert not hasattr(controller, "link")


@pytest.mark.asyncio
async def test_controller_requires_explicit_radio_backend():
    with pytest.raises(TypeError, match='backend'):
        Controller('missing')
