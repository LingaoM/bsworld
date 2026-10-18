# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

from types import SimpleNamespace

import pytest

from bscontroller import hci
from bscontroller.hci.backend import RadioBackend
from bscontroller.hci.controller import Controller
from bscontroller.linklayer.connection import Connection as RadioConnection
from bscontroller_tests.unit.helpers import PARAMETERS

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
