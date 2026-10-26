# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Ownership contracts between HCI, LL procedures, event execution and radio scheduling."""

import subprocess
import sys
from types import SimpleNamespace

import pytest

from bscontroller import hci
from bscontroller.address import Address
from bscontroller.errors import ErrorCode
from bscontroller.linklayer import PDU_DATA_NESN_MASK, PDU_DATA_SN_MASK, LlId
from bscontroller.linklayer import ControlOpcode as Opcode
from bscontroller.linklayer.connection import Connection
from bscontroller.linklayer.discovery import Advertising, PeriodicSync
from bscontroller.linklayer.encryption import ENC_REQUEST
from bscontroller.linklayer.link import RadioLink
from bscontroller.linklayer.service import LinkLayerService
from bscontroller.linklayer.state import Role
from tests.unit.helpers import PARAMETERS, FakeRadio


@pytest.mark.parametrize('module', ['service', 'connection_event', 'resource', 'link'])
def test_ll_modules_do_not_load_hci_or_runtime(module):
    # Run in a fresh interpreter: the fixture's Host codec must not conceal a dependency.
    subprocess.run(
        [
            sys.executable,
            '-c',
            f"import sys, importlib; importlib.import_module('bscontroller.linklayer.{module}'); assert not any(name == prefix or name.startswith(prefix + '.') for name in sys.modules for prefix in ('bscontroller.hci', 'bscontroller.runtime'))",
        ],
        check=True,
    )


def test_ll_creates_connection_with_defaults_before_notifying_upper_layer():
    observed = []
    listener = SimpleNamespace(
        allocate_connection_handle=lambda: 1,
        trace=lambda message: None,
        on_connected=lambda connection: observed.append((connection.controls.tx_phys, connection.controls.rx_phys)),
    )
    link = RadioLink(FakeRadio(), listener)
    service = LinkLayerService(link, Address.ANY, 30_000, 20_000)
    service.set_default_phys(2, 4)
    connection = Connection(link, PARAMETERS, Address.ANY, Role.PERIPHERAL, 0)
    connection.report_created()
    assert observed == [(2, 4)]


def test_hci_scan_configuration_is_a_detached_view(controller):
    commands = controller.le_procedures
    commands.ll.enable_scanning(True)
    view = commands.scan_parameters
    view.start_us = 123456
    view.backoff.count = 42
    assert commands.ll.scan_parameters.start_us == 0
    assert commands.ll.scan_parameters.backoff.count == 1


def test_ll_filter_admission_does_not_depend_on_hci_validation(controller):
    service = controller.le_procedures.ll
    service.configure_scanning(Address.ANY, 30_000, 20_000, False, 1)
    service.enable_scanning(True)
    assert service.edit_filter(Address.ANY, True, 8) == ErrorCode.COMMAND_DISALLOWED_ERROR
    assert not service.link.accept_list


def test_ll_rejects_reconfiguration_of_an_active_advertiser(controller):
    service = controller.le_procedures.ll.advertising
    original = Advertising(Address.ANY, enabled=True, data=b'original')
    service.link.advertisers[0] = original
    candidate = Advertising(Address.ANY, data=b'replacement')
    assert service.configure(0, candidate) == ErrorCode.COMMAND_DISALLOWED_ERROR
    assert service.link.advertisers[0] is original and original.data == b'original'


def test_sync_cancellation_releases_ll_state_before_notification(controller):
    service = controller.le_procedures.ll
    sync = PeriodicSync(Address.ANY, 1, 100_000, 0)
    service.start_synchronizing(sync)
    assert service.cancel_synchronizing() is sync
    assert service.link.sync is None
    replacement = PeriodicSync(Address.ANY, 2, 100_000, 0)
    service.start_synchronizing(replacement)
    assert service.link.sync is replacement


def test_radio_claim_restores_previous_deadline_after_failure(connection, monkeypatch):
    resource = connection.link.resource
    resource.deadline_us = 123
    monkeypatch.setattr(resource, 'radio_limit', lambda owner=None: 77)
    with pytest.raises(RuntimeError, match='event failed'):
        with resource.claim(connection):
            assert resource.deadline_us == 77
            raise RuntimeError('event failed')
    assert resource.deadline_us == 123


@pytest.mark.parametrize('operation', ['features', 'version'])
def test_cached_procedure_completion_follows_command_status(connection, operation):
    connection.report_created()
    controller = connection.link.listener.controller
    if operation == 'features':
        connection.peer_features = 0
        command = hci.HCI_LE_Read_Remote_Features_Command(connection.handle)
        event_type = hci.HCI_LE_Read_Remote_Features_Complete_Event
    else:
        connection.controls.peer_version = (9, 1, 1)
        command = hci.HCI_Read_Remote_Version_Information_Command(connection.handle)
        event_type = hci.HCI_Read_Remote_Version_Information_Complete_Event
    controller.events.clear()
    controller.on_packet(bytes(command))
    assert isinstance(controller.events[0], hci.HCI_Command_Status_Event)
    assert controller.events[0].status == ErrorCode.SUCCESS
    assert isinstance(controller.events[1], event_type)


@pytest.mark.asyncio
async def test_completed_control_exchange_cannot_authorize_a_later_unknown_response(connection):
    connection.established = True
    connection.report_created()
    connection.controls.request_phy(1, 1)
    await connection.send(0, 100)
    response = bytes([Opcode.LL_PHY_UPDATE_IND, 0, 0, 0, 0])
    connection.accept(bytes([LlId.CONTROL | PDU_DATA_NESN_MASK, len(response)]) + response, True)
    assert not connection.controls.phy_request
    assert not connection.llcp.local_exchanges
    connection.control(bytes([Opcode.LL_ENC_REQ]) + ENC_REQUEST.pack(bytes(8), 0, bytes(8), bytes(4)))
    await connection.send(0, connection.radio.now_us + 100)
    unknown = bytes([Opcode.LL_UNKNOWN_RSP, Opcode.LL_PHY_REQ])
    connection.accept(bytes([LlId.CONTROL | PDU_DATA_SN_MASK, len(unknown)]) + unknown, True)
    assert connection.closed
    assert (
        connection.link.listener.controller.events[-1].reason
        == ErrorCode.CONNECTION_TERMINATED_DUE_TO_MIC_FAILURE_ERROR
    )


@pytest.mark.asyncio
async def test_legacy_rejection_releases_its_tracked_exchange(connection):
    connection.report_created()
    connection.controls.request_parameters(24, 24, 0, 100)
    await connection.send(0, 100)
    assert Opcode.LL_CONNECTION_PARAM_REQ in connection.llcp.local_exchanges
    rejection = bytes([Opcode.LL_REJECT_IND, ErrorCode.DIFFERENT_TRANSACTION_COLLISION_ERROR])
    connection.accept(bytes([LlId.CONTROL | PDU_DATA_NESN_MASK, len(rejection)]) + rejection, True)
    assert not connection.llcp.local_exchanges
    assert not connection.controls.parameter_request


def test_ll_does_not_replace_an_existing_sync_acquisition(controller):
    service = controller.le_procedures.ll
    first = PeriodicSync(Address.ANY, 1, 100_000, 0)
    replacement = PeriodicSync(Address.ANY, 2, 100_000, 0)
    assert service.start_synchronizing(first) == ErrorCode.SUCCESS
    assert service.start_synchronizing(replacement) == ErrorCode.COMMAND_DISALLOWED_ERROR
    assert service.link.sync is first


@pytest.mark.asyncio
async def test_reply_to_peer_version_is_not_tracked_as_a_local_request(connection):
    connection.report_created()
    connection.control(bytes([Opcode.LL_VERSION_IND, 9, 1, 0, 1, 0]))
    await connection.send(0, 100)
    assert not connection.llcp.local_exchanges


def test_phy_rejection_cannot_stop_an_automatically_accepted_parameter_timer(connection):
    from bscontroller.linklayer.control import PARAM_REQUEST

    controls = connection.controls
    controls.request_phy(1, 1)
    # Identical parameters are accepted without a Host round trip. The Peripheral
    # still owes the Central a response and must await UPDATE_IND afterwards.
    request = bytes([Opcode.LL_CONNECTION_PARAM_REQ]) + PARAM_REQUEST.pack(24, 24, 0, 100, 0, 0, *([0xFFFF] * 6))
    controls.control(request)
    deadline = controls.deadline_us
    assert not controls.remote_parameters and not controls.requested_interval_min
    controls.control(bytes([Opcode.LL_UNKNOWN_RSP, Opcode.LL_PHY_REQ]))
    assert controls.deadline_us == deadline
    connection.radio.now_us = deadline
    assert controls.check_timeout() and connection.closed
