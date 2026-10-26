# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Role lifetimes commit independently of HCI and RF event execution."""

from dataclasses import replace

import pytest

from bscontroller.address import Address
from bscontroller.errors import ErrorCode
from bscontroller.linklayer import (
    PDU_ADV_RXADD_MASK,
    PDU_ADV_TXADD_MASK,
    AdvertisingMode,
    AdvertisingPduType,
)
from bscontroller.linklayer.advertising import ExtendedPdu, SyncInfo
from bscontroller.linklayer.discovery import (
    Advertising,
    Initiating,
    PeriodicSync,
    Scanning,
)
from bscontroller.linklayer.link import RadioLink
from bscontroller.linklayer.parameters import Parameters
from bscontroller.linklayer.resource import RadioResourceManager
from bscontroller.linklayer.results import (
    ConnectionAccepted,
    PeriodicPacketReceived,
    SyncInfoReceived,
)
from bscontroller.linklayer.scheduler import RadioPriority, RadioReservation
from bscontroller.linklayer.state import DataStatus, Role
from bscontroller.radio.base import Received


class ClockRadio:
    now_us = 0

    async def advance_to_us(self, target_us):
        self.now_us = target_us
        return target_us


class Recorder:
    """An internal LL listener with no HCI objects or handle allocator."""

    local_version = (14, 0, 0)

    def __init__(self):
        self.events = []

    def trace(self, message):
        pass

    def on_connected(self, connection):
        assert connection.link.connections[connection.handle] is connection
        self.events.append(('connected', connection.handle))

    def on_advertising_ended(self, item, status):
        assert not item.enabled
        self.events.append(('advertising-ended', status))

    def on_scan_timeout(self):
        self.events.append(('scan-timeout',))

    def on_scan_period(self):
        self.events.append(('scan-period',))

    def on_sync_established(self, sync, status):
        self.events.append(('sync-established', sync.handle, status))

    def on_sync_lost(self, sync):
        self.events.append(('sync-lost', sync.handle))

    def on_periodic_report(self, sync, data, rssi, tx_power, status):
        self.events.append(('periodic-report', sync.handle, data))


@pytest.fixture
def link():
    return RadioLink(ClockRadio(), Recorder())


def connection_result(peer, advertiser=None):
    return ConnectionAccepted(
        Parameters(0x9A328370, 0x123456, 1, 0, 24, 0, 100, (1 << 37) - 1, 7),
        Address(peer),
        Role.PERIPHERAL,
        500,
        Address('F0:F1:F2:F3:F4:01'),
        True,
        advertiser,
    )


def test_connection_commit_owns_handle_and_stops_the_advertiser_before_notification(
    link,
):
    item = Advertising(Address('F0:F1:F2:F3:F4:01'), enabled=True, events=7)
    link.roles.advertising.publish(4, item)
    connection = link.roles.connections.accepted(
        connection_result('C0:11:22:33:44:55', item)
    )
    assert connection.handle == 1
    assert not item.enabled
    assert connection.advertising_handle == 4
    assert connection.advertising_events == 7
    assert link.listener.events == [('connected', 1)]
    second = link.roles.connections.accepted(connection_result('C0:11:22:33:44:66'))
    assert second.handle == 2
    del link.connections[connection.handle]
    assert link.roles.connections.allocate_handle() == 1


def test_delayed_connection_result_cannot_complete_a_newer_initiation(link):
    result = connection_result('C0:11:22:33:44:55')
    original = Initiating(
        result.self_address, result.peer, 20, 10, result.parameters, 0
    )
    current = replace(original, start_us=100)
    link.roles.scanning.start_initiating(current)
    delayed = replace(result, role=Role.CENTRAL, initiator=original)
    assert link.roles.connections.accepted(delayed) is None
    assert link.roles.scanning.initiating is current
    assert not link.connections and not link.listener.events
    connection = link.roles.connections.accepted(replace(delayed, initiator=current))
    assert connection.handle == 1
    assert link.roles.scanning.initiating is None


@pytest.mark.asyncio
async def test_received_packet_from_an_old_window_cannot_start_a_new_initiation(link):
    result = connection_result('C0:11:22:33:44:55')
    original = Initiating(
        result.self_address, result.peer, 20000, 10000, result.parameters, 0
    )
    current = replace(original, start_us=100)
    scanning = link.roles.scanning
    scanning.start_initiating(original)
    sent = []
    header = AdvertisingPduType.ADV_IND | (
        PDU_ADV_TXADD_MASK if result.peer.is_random else 0
    )
    packet = Received(bytes([header, 6]) + bytes(result.peer), -40, 100, 200, True)

    async def receive(channel, until_us, **parameters):
        scanning.cancel_initiating()
        scanning.start_initiating(current)
        link.radio.now_us = packet.end_us
        return packet

    async def transmit(channel, pdu, **parameters):
        sent.append(pdu)
        return packet.end_us + 500

    link.radio.receive = receive
    link.radio.transmit = transmit
    await scanning.run(original, 1000)
    assert scanning.initiating is current
    assert not link.connections and not sent and not link.listener.events


def test_old_connection_cannot_release_a_reused_handle(link):
    manager = link.roles.connections
    old = manager.accepted(connection_result('C0:11:22:33:44:55'))
    assert manager.release(old)
    current = manager.accepted(connection_result('C0:11:22:33:44:66'))
    assert old.handle == current.handle
    assert manager.release(old) is False
    assert manager.contexts[current.handle] is current


@pytest.mark.asyncio
@pytest.mark.parametrize('action', ['reset', 'disable', 'remove', 'replace'])
async def test_aux_response_cannot_commit_an_advertiser_released_during_tx(
    link, action
):
    result = connection_result('C0:11:22:33:44:55')
    item = Advertising(
        result.self_address,
        enabled=True,
        extended=True,
        mode=AdvertisingMode.CONNECTABLE,
    )
    advertising = link.roles.advertising
    advertising.publish(4, item)
    payload = (
        bytes(result.peer) + bytes(result.self_address) + result.parameters.encode()
    )
    header = AdvertisingPduType.CONNECT_IND
    if result.peer.is_random:
        header |= PDU_ADV_TXADD_MASK
    if result.self_address.is_random:
        header |= PDU_ADV_RXADD_MASK
    packet = Received(bytes([header, len(payload)]) + payload, -40, 100, 200, True)

    async def transmit(channel, pdu, **parameters):
        if action == 'reset':
            link.reset()
        elif action == 'disable':
            item.enabled = False
        elif action == 'remove':
            advertising.remove(4)
        else:
            advertising.publish(4, replace(item))
        return 500

    link.radio.transmit = transmit
    assert await link.extended.request(item, 1, packet)
    assert not link.connections and not link.listener.events
    if action == 'replace':
        assert advertising.contexts[4] is not item
        assert advertising.contexts[4].enabled


def test_syncinfo_is_only_acquisition_and_a_valid_packet_commits_establishment(link):
    address = Address('C0:11:22:33:44:55')
    sync = PeriodicSync(address, 2, 100_000, 100_000)
    manager = link.roles.synchronization
    manager.start(sync)
    info = SyncInfo(9000, 80, (1 << 37) - 1, 0x456789AB, 0x123456, 4)
    packet = Received(b'', -40, 100, 200, True)
    manager.acquired(SyncInfoReceived(Address('C0:11:22:33:44:66'), 2, info, packet))
    assert sync.info is None
    manager.acquired(SyncInfoReceived(address, 2, info, packet))
    assert manager.pending is sync and not sync.established
    assert sync.next_us == 9100 and sync.counter == 4
    assert not manager.active and not link.listener.events

    def established(item, status):
        assert manager.pending is None
        assert manager.active[item.handle] is item and item.established
        link.listener.events.append(('sync-established', item.handle, status))

    link.listener.on_sync_established = established
    periodic = Received(b'', -40, 9200, 9300, True)
    result = PeriodicPacketReceived(sync, periodic, ExtendedPdu())
    manager.received(result)
    manager.received(result)
    assert sync.next_us == 9200 and sync.deadline_us == 109300
    assert link.listener.events == [('sync-established', 1, ErrorCode.SUCCESS)]


def test_delayed_periodic_result_cannot_revive_cancelled_acquisition(link):
    manager = link.roles.synchronization
    original = PeriodicSync(Address('C0:11:22:33:44:55'), 2, 100_000, 100_000)
    manager.start(original)
    manager.cancel()
    current = replace(original)
    manager.start(current)
    result = PeriodicPacketReceived(
        original, Received(b'', -40, 100, 200, True), ExtendedPdu()
    )
    assert manager.received(result) is False
    assert manager.pending is current and not manager.active
    assert not original.established and not link.listener.events


def test_removed_sync_cannot_publish_later_fragments(link):
    manager = link.roles.synchronization
    sync = PeriodicSync(
        Address('C0:11:22:33:44:55'), 2, 100_000, 100_000, established=True, handle=1
    )
    manager.active[1] = sync

    def report(item, data, rssi, tx_power, status):
        link.listener.events.append(data)
        manager.terminate(item.handle)

    link.listener.on_periodic_report = report
    manager.report(sync, b'first', -40, None, DataStatus.INCOMPLETE)
    manager.report(sync, b'stale', -40, None, DataStatus.COMPLETE)
    assert link.listener.events == [b'first']


def test_advertising_event_limit_does_not_stop_the_independent_periodic_train(link):
    item = Advertising(
        Address('F0:F1:F2:F3:F4:01'),
        enabled=True,
        events=3,
        max_events=3,
        periodic_enabled=True,
        periodic_interval=80,
        periodic_next_us=10000,
    )
    link.roles.advertising.publish(1, item)
    operations = link.roles.advertising.prepare()
    assert [operation.priority for operation in operations] == [
        RadioPriority.PERIODIC_TX
    ]
    assert link.listener.events == [
        ('advertising-ended', ErrorCode.LIMIT_REACHED_ERROR)
    ]
    link.roles.advertising.prepare()
    assert len(link.listener.events) == 1 and item.periodic_enabled


@pytest.mark.parametrize('action', ['reset', 'remove'])
def test_advertising_completion_callback_cannot_prepare_a_released_context(
    link, action
):
    manager = link.roles.advertising
    first = Advertising(Address('F0:F1:F2:F3:F4:01'), enabled=True, deadline_us=10)
    second = replace(first, periodic_enabled=True, periodic_interval=80)
    manager.publish(1, first)
    manager.publish(2, second)
    link.radio.now_us = 10

    def ended(item, status):
        link.listener.events.append(item)
        if action == 'reset':
            link.reset()
        else:
            manager.remove(2)

    link.listener.on_advertising_ended = ended
    assert not manager.prepare()
    assert link.listener.events == [first]
    manager.expire(second, ErrorCode.ADVERTISING_TIMEOUT_ERROR)
    assert link.listener.events == [first]


@pytest.mark.asyncio
@pytest.mark.parametrize('period_us', [0, 100])
async def test_scan_owner_distinguishes_timeout_from_a_period_gap(link, period_us):
    scan = Scanning(
        Address('F0:F1:F2:F3:F4:01'),
        20,
        10,
        duration_us=10,
        period_us=period_us,
        deadline_us=10,
    )
    manager = link.roles.scanning
    manager.enable(scan)
    link.radio.now_us = 10
    await manager.run(scan, 20)
    if period_us:
        assert manager.active is scan
        assert scan.start_us == 100 and scan.deadline_us == 110
        assert link.radio.now_us == 20
        assert link.listener.events == [('scan-period',)]
    else:
        assert manager.active is None
        assert link.listener.events == [('scan-timeout',)]


def test_sync_expiry_is_processed_without_a_radio_receive(link):
    manager = link.roles.synchronization
    info = SyncInfo(9000, 80, (1 << 37) - 1, 0x456789AB, 0x123456, 0)
    pending = PeriodicSync(
        Address('C0:11:22:33:44:55'), 2, 100_000, 20, info=info, handle=1
    )
    manager.pending = pending
    manager.active[2] = replace(pending, established=True, handle=2)
    link.radio.now_us = 20
    manager.expire()
    assert manager.pending is None and not manager.active
    assert link.listener.events == [
        ('sync-established', 1, ErrorCode.CONNECTION_FAILED_TO_BE_ESTABLISHED_ERROR),
        ('sync-lost', 2),
    ]


def test_radio_admission_only_needs_clock_and_published_windows():
    owner = object()
    reservations = [RadioReservation(30, 10, 100, RadioPriority.CONNECTION)]
    resource = RadioResourceManager(
        lambda: 10, lambda exclude: ([] if exclude is owner else reservations)
    )
    assert resource.admit(owner, 30, 40, RadioPriority.PERIODIC_RX)
    assert not resource.admit(object(), 30, 40, RadioPriority.PERIODIC_RX)
    assert not resource.admit(owner, 30, 40, RadioPriority.PERIODIC_RX, earliest_us=31)
    with pytest.raises(RuntimeError), resource.claim():
        assert resource.deadline_us == 30
        raise RuntimeError('event aborted')
    assert resource.deadline_us is None
