# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Ownership checks at the decoded HCI / Link Layer service boundary."""

import ast
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from bscontroller import hci
from bscontroller.address import Address
from bscontroller.linklayer.api import AdvertisingConfig, ConnectionSnapshot
from bscontroller.linklayer.discovery import Advertising


def test_read_advertising_power_does_not_create_or_reconfigure_ll_state(controller):
    commands = controller.le_procedures
    assert commands.ll.advertising.snapshot(-1) is None
    result = commands.on_hci_le_read_advertising_physical_channel_tx_power_command(
        hci.HCI_LE_Read_Advertising_Physical_Channel_Tx_Power_Command()
    )
    assert result.status == hci.HCI_ErrorCode.SUCCESS
    assert result.tx_power_level == 0
    assert commands.ll.advertising.snapshot(-1) is None


def test_advertising_configuration_cannot_replace_runtime_state(controller):
    service = controller.le_procedures.ll.advertising
    config = AdvertisingConfig(controller.public_address)
    assert service.configure(0, config) == hci.HCI_ErrorCode.SUCCESS
    live = controller.backend.link.advertisers[0]
    live.periodic_counter = 17
    live.periodic_aa = 0x12345678
    live.events = 9
    live.next_us = 5000
    service.store_data(0, 'data', b'payload')
    assert (
        service.configure(0, replace(config, tx_power_dbm=-8))
        == hci.HCI_ErrorCode.SUCCESS
    )
    updated = controller.backend.link.advertisers[0]
    assert (updated.periodic_counter, updated.periodic_aa) == (17, 0x12345678)
    assert (updated.events, updated.next_us) == (9, 5000)
    assert service.snapshot(0).data == b'payload'
    assert service.snapshot(0).tx_power_dbm == -8
    with pytest.raises(TypeError, match='must not contain live state'):
        service.configure(0, Advertising(controller.public_address))
    with pytest.raises(FrozenInstanceError):
        config.address.address_type = hci.AddressType.RANDOM_DEVICE


def test_legacy_data_update_retains_the_context_held_by_a_radio_event(controller):
    commands = controller.le_procedures
    assert (
        commands.on_hci_le_set_advertising_enable_command(
            hci.HCI_LE_Set_Advertising_Enable_Command(1)
        ).status
        == hci.HCI_ErrorCode.SUCCESS
    )
    executing = controller.backend.link.advertisers[-1]
    assert (
        commands.on_hci_le_set_advertising_data_command(
            hci.HCI_LE_Set_Advertising_Data_Command(b'updated')
        ).status
        == hci.HCI_ErrorCode.SUCCESS
    )
    assert controller.backend.link.advertisers[-1] is executing
    assert executing.enabled and bytes(executing.data) == b'updated'


def test_connection_queries_are_frozen_detached_values(connection):
    connection.report_created()
    service = connection.link.listener.sink.ll
    before = service.connection_snapshot(connection.handle)
    assert isinstance(before, ConnectionSnapshot)
    assert not any(
        hasattr(before, name) for name in ('controls', 'encryption', 'event', 'link')
    )
    with pytest.raises(FrozenInstanceError):
        before.rssi = -20
    with pytest.raises(FrozenInstanceError):
        before.peer.address_type = hci.AddressType.RANDOM_DEVICE
    connection.rssi = -42
    assert before.rssi is None
    assert service.connection_snapshot(connection.handle).rssi == -42


@pytest.mark.parametrize('operation', ['scan', 'scan_reset', 'advertising_address'])
def test_ll_configuration_copies_mutable_input_addresses(controller, operation):
    service = controller.le_procedures.ll
    supplied = Address('C0:12:34:56:78:9A')
    expected = bytes(supplied), supplied.address_type
    if operation == 'scan':
        service.configure_scanning(supplied, 30_000, 20_000, False, 0)
    elif operation == 'scan_reset':
        service.reset_configuration(supplied)
    else:
        service.advertising.configure(0, AdvertisingConfig(supplied))
        assert service.advertising.set_random_address(0, supplied) == 0
    supplied.address_bytes = bytes(6)
    supplied.address_type = hci.AddressType.PUBLIC_DEVICE
    if operation.startswith('scan'):
        actual = service.scan_parameters.address
        service.enable_scanning(True)
        assert controller.backend.link.scan.address == actual
    else:
        snapshot = service.advertising.snapshot(0)
        actual = snapshot.random_address
        assert snapshot.address == actual
    assert (bytes(actual), actual.address_type) == expected


@pytest.mark.parametrize('periodic', [False, True])
def test_filter_lists_copy_address_keys_before_the_caller_changes_them(
    controller, periodic
):
    service = controller.le_procedures.ll
    supplied = Address('C0:12:34:56:78:9A')
    expected = Address(bytes(supplied), supplied.address_type)
    if periodic:
        assert service.edit_periodic_list((supplied, 3), True, 8) == 0
    else:
        assert service.edit_filter(supplied, True, 8) == 0
    supplied.address_bytes = bytes(6)
    supplied.address_type = hci.AddressType.PUBLIC_DEVICE
    if periodic:
        assert service.edit_periodic_list((expected, 3), False, 8) == 0
        assert not controller.backend.link.periodic_advertiser_list
    else:
        assert expected in controller.backend.link.accept_list
        assert service.edit_filter(expected, False, 8) == 0
        assert not controller.backend.link.accept_list


def test_ll_callback_passes_a_snapshot_without_sharing_connection_state(
    connection, monkeypatch
):
    observed = []
    sink = connection.link.listener.sink
    monkeypatch.setattr(
        sink, 'on_remote_features', lambda value, status: observed.append(value)
    )
    connection.link.listener.on_remote_features(connection, 0)
    connection.peer_features = 0x1234
    assert len(observed) == 1
    assert isinstance(observed[0], ConnectionSnapshot)
    assert observed[0].peer_features is None


def test_masked_remote_parameter_request_uses_the_ll_service(connection, monkeypatch):
    connection.report_created()
    commands = connection.link.listener.sink
    commands.controller.le_event_mask = 0
    rejected = []
    monkeypatch.setattr(
        commands.ll,
        'reject_parameters',
        lambda handle, reason: rejected.append((handle, reason)),
    )
    commands.on_remote_parameters(
        commands.ll.connection_snapshot(connection.handle), 24, 24, 0, 100
    )
    assert rejected == [
        (connection.handle, hci.HCI_ErrorCode.UNSUPPORTED_REMOTE_FEATURE_ERROR)
    ]


def test_hci_does_not_enter_live_ll_collections_or_procedure_objects():
    import bscontroller.hci as package

    forbidden = {
        'advertisers',
        'connections',
        'syncs',
        'scan',
        'initiating',
        'sync',
        'controls',
        'encryption',
        'packet_security',
    }
    for source in Path(package.__file__).parent.glob('*.py'):
        for node in ast.walk(ast.parse(source.read_text())):
            if isinstance(node, ast.Attribute):
                assert node.attr not in forbidden, (source.name, node.lineno, node.attr)
