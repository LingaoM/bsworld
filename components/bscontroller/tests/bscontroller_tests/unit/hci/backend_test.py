# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""HCI decoding, backend isolation and binding ownership."""

from types import SimpleNamespace

import pytest

from bscontroller import hci
from bscontroller.hci.backend import RadioBackend
from bscontroller.hci.capabilities import HCI_ACL_BUFFER_SIZE
from bscontroller.hci.controller import Controller

ErrorCode = hci.HCI_ErrorCode

ADDRESS = hci.Address('F0:F1:F2:F3:F4:01', hci.AddressType.PUBLIC_DEVICE)


def radio_backend():
    return RadioBackend(SimpleNamespace(now_us=0))


@pytest.mark.asyncio
async def test_backend_capabilities_do_not_change_other_controllers():
    local = Controller('first', backend=radio_backend())
    supported = local.supported_commands.copy()
    radio = Controller('radio', backend=radio_backend())
    assert radio.le_features & hci.LeFeatureMask.LE_PERIODIC_ADVERTISING
    assert radio.le_features & hci.LeFeatureMask.LE_ENCRYPTION
    assert radio.le_features & hci.LeFeatureMask.MINIMUM_NUMBER_OF_USED_CHANNELS_PROCEDURE
    assert radio.le_acl_data_packet_length == HCI_ACL_BUFFER_SIZE
    assert local.le_features & hci.LeFeatureMask.LE_ENCRYPTION
    assert local.supported_commands == supported


@pytest.mark.asyncio
async def test_backend_cannot_be_shared_by_controller_instances():
    backend = radio_backend()
    Controller('first', backend=backend)
    with pytest.raises(ValueError, match='one Controller'):
        Controller('second', backend=backend)
