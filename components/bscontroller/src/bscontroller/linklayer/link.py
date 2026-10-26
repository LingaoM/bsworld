# Adapted for the independent BSController package.
# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""LE radio procedures; no HCI serialization, transport, or simulator binding."""

from __future__ import annotations

import random
from dataclasses import replace
from functools import partial

from bscontroller.address import Address
from bscontroller.capabilities import (
    CONTROLLER_CONNECTION_COUNT,
    CONTROLLER_SUPPORTED_PHY_MASK,
)
from bscontroller.errors import ErrorCode
from bscontroller.linklayer import (
    LL_ADV_DELAY_MAX_US,
    LL_ADV_PRIMARY_CHANNELS,
    LL_CONN_INTERVAL_UNIT_US,
    LL_EVENT_COUNTER_MASK,
    LL_HOP_INCREMENT_MAX,
    LL_HOP_INCREMENT_MIN,
    LL_IFS_US,
    LL_MAFS_US,
    LL_PERIODIC_INTERVAL_UNIT_US,
    LL_PERIODIC_SYNC_ESTABLISHMENT_EVENTS,
    PDU_CRC_SIZE,
    PDU_DATA_PAYLOAD_SIZE_MIN,
    PDU_DATA_PAYLOAD_TIME_MIN_US,
    PDU_HEADER_SIZE,
)
from bscontroller.linklayer.bitstream import generate_access_address
from bscontroller.linklayer.connection import Connection
from bscontroller.linklayer.discovery import (
    Advertising,
    Initiating,
    PeriodicSync,
    Scanning,
    ScanWindow,
    scan_window_at,
)
from bscontroller.linklayer.extended import ExtendedProcedures, periodic_time_us
from bscontroller.linklayer.listener import Listener as Listener
from bscontroller.linklayer.parameters import Parameters
from bscontroller.linklayer.periodic import periodic_receive, periodic_transmit
from bscontroller.linklayer.primary import (
    advertise_legacy,
    advertising_event_time_us,
    advertising_request,
    initiate,
    scan_extended,
    scan_packet,
)
from bscontroller.linklayer.resource import (
    PendingOperation,
    RadioResourceManager,
    periodic_receive_window,
    periodic_transmit_start_us,
)
from bscontroller.linklayer.resource import (
    connection_window as connection_window,
)
from bscontroller.linklayer.resource import (
    periodic_transmit_window as periodic_transmit_window,
)
from bscontroller.linklayer.scheduler import (
    RadioPriority,
    RadioReservation,
    first_radio_gap,
)
from bscontroller.linklayer.state import Role
from bscontroller.linklayer.timing import (
    LL_CONN_EVENT_GUARD_US,
    LL_DEFAULT_SCAN_INTERVAL_US,
    LL_RESPONSE_START_TOLERANCE_US,
)
from bscontroller.radio.base import (
    PHY_OCTET_BITS,
    RADIO_SWITCH_TIME_US,
    Phy,
    Radio,
    Received,
)


class RadioLink:
    """One physical radio, with explicit, integer-microsecond operation deadlines."""

    # Bound stateless procedures use this link's radio and active contexts.
    _advertising_request = advertising_request
    _initiate = initiate
    _scan_packet = scan_packet
    _scan_extended = scan_extended
    _periodic_transmit = periodic_transmit
    _periodic_receive = periodic_receive

    def __init__(
        self, radio: Radio, listener: Listener, features: int = 0, seed: int = 1
    ):
        self.radio = radio
        self.listener = listener
        self.features = features
        self.default_tx_phys = self.default_rx_phys = CONTROLLER_SUPPORTED_PHY_MASK
        self.advertisers: dict[int, Advertising] = {}
        self.scan: Scanning | None = None
        self.initiating: Initiating | None = None
        self.connections: dict[int, Connection] = {}
        self.sync: PeriodicSync | None = None
        self.syncs: dict[int, PeriodicSync] = {}
        self.seed = seed
        self.random = random.Random(seed)
        self.extended = ExtendedProcedures(self)
        self.resource = RadioResourceManager(self)
        self.scan_cursor = 0
        self.accept_list: set[Address] = set()
        self.periodic_advertiser_list: set[tuple[Address, int]] = set()
        self.default_tx_octets = PDU_DATA_PAYLOAD_SIZE_MIN
        self.default_tx_time = PDU_DATA_PAYLOAD_TIME_MIN_US

    @property
    def radio_deadline_us(self) -> int | None:
        return self.resource.deadline_us

    @radio_deadline_us.setter
    def radio_deadline_us(self, value: int | None) -> None:
        self.resource.deadline_us = value

    def trace(self, message: str) -> None:
        self.listener.trace(message)

    def reset(self) -> None:
        self.advertisers.clear()
        self.scan = self.initiating = self.sync = None
        self.connections.clear()
        self.syncs.clear()
        self.radio_deadline_us = None
        self.scan_cursor = 0
        self.random.seed(self.seed)
        self.accept_list.clear()
        self.periodic_advertiser_list.clear()
        self.default_tx_octets = PDU_DATA_PAYLOAD_SIZE_MIN
        self.default_tx_time = PDU_DATA_PAYLOAD_TIME_MIN_US

    @property
    def now_us(self) -> int:
        return self.radio.now_us

    def can_connect(self, peer: Address) -> bool:
        return len(self.connections) < CONTROLLER_CONNECTION_COUNT and not any(
            connection.peer == peer for connection in self.connections.values()
        )

    def create_connection(
        self,
        parameters: Parameters,
        peer: Address,
        role: Role,
        connect_end_us: int,
        *,
        self_address: Address,
        csa2: bool,
        advertiser: Advertising | None = None,
        window_delay_us: int = LL_CONN_INTERVAL_UNIT_US,
        phy: Phy = Phy.LE_1M,
    ) -> Connection:
        """Enter the Connection state in the given role (Core Vol 6, Part B, 4.5.4,
        4.5.5).
        """
        if advertiser is not None:
            advertiser.enabled = False
        connection = Connection(
            self,
            parameters,
            peer,
            role,
            connect_end_us,
            csa2=csa2,
            self_address=self_address,
            window_delay_us=window_delay_us,
            phy=phy,
        )
        if advertiser is not None:
            handle = next(
                key for key, value in self.advertisers.items() if value is advertiser
            )
            if handle != -1:
                connection.advertising_handle = handle
                connection.advertising_events = advertiser.events
        self.connections[connection.handle] = connection
        connection.report_created()
        return connection

    def new_access_address(self) -> int:
        used = {
            connection.parameters.access_address
            for connection in self.connections.values()
        }
        used.update(
            item.periodic_aa
            for item in self.advertisers.values()
            if item.periodic_enabled
        )
        return generate_access_address(self.random, used)

    def reservations(self, *, exclude: object = None) -> list[RadioReservation]:
        return self.resource.reservations(exclude=exclude)

    def _sync_contexts(self, sync: PeriodicSync | None) -> list[PeriodicSync]:
        return list(self.syncs.values()) + ([sync] if sync else [])

    def connection_parameters(
        self,
        parameters: Parameters,
        request_end_us: int,
        window_delay_us: int,
        phy: Phy = Phy.LE_1M,
    ) -> Parameters | None:
        """Allocate independent wire identity and a legal initial transmit window."""
        start = request_end_us + window_delay_us
        # Reserve the larger of the initial window and a complete exchange, plus
        # a guard. Keep the chosen offset on the 1.25-ms grid (Vol 6, Part B, 4.5.3).
        gap = first_radio_gap(
            self.reservations(),
            start,
            max(
                parameters.window_size * LL_CONN_INTERVAL_UNIT_US,
                2 * phy.airtime_us(PDU_HEADER_SIZE + PDU_DATA_PAYLOAD_SIZE_MIN)
                + 2 * LL_IFS_US,
            )
            + LL_CONN_EVENT_GUARD_US,
            start
            + (parameters.interval - parameters.window_size) * LL_CONN_INTERVAL_UNIT_US,
            quantum_us=LL_CONN_INTERVAL_UNIT_US,
        )
        if gap is None:
            return None
        return replace(
            parameters,
            window_offset=(gap - start) // LL_CONN_INTERVAL_UNIT_US,
            access_address=self.new_access_address(),
            crc_init=self.random.getrandbits(PDU_CRC_SIZE * PHY_OCTET_BITS),
            hop=self.random.randint(LL_HOP_INCREMENT_MIN, LL_HOP_INCREMENT_MAX),
        )

    def set_periodic_enabled(self, item: Advertising, enable: bool) -> None:
        """Start or stop a periodic train with a fresh Access Address and CRCInit (Core
        Vol 6, Part B, 4.4.2.12, 2.1.2).
        """
        if item.periodic_enabled == enable:
            return
        interval_us = item.periodic_interval * LL_PERIODIC_INTERVAL_UNIT_US
        next_us = self.now_us + interval_us
        if enable:
            duration_us = periodic_time_us(item) + LL_MAFS_US
            phase = first_radio_gap(
                self.reservations(exclude=item),
                next_us,
                duration_us,
                next_us + interval_us - duration_us,
            )
            # Scheduling conflicts may lose events, not disable legal states.
            if phase is not None:
                next_us = phase
            item.periodic_aa = self.new_access_address()
            item.periodic_crc = self.random.getrandbits(PDU_CRC_SIZE * PHY_OCTET_BITS)
        item.periodic_enabled = enable
        item.periodic_next_us = next_us
        item.periodic_counter = 0

    def fits_radio(self, end_us: int) -> bool:
        return self.resource.fits_radio(end_us)

    def radio_limit(self, owner: object = None) -> int | None:
        return self.resource.radio_limit(owner)

    async def _transmit(self, channel: int, pdu: bytes, **kwargs) -> int:
        self.trace(f'RADIO TX ch={channel} pdu={pdu.hex()}')
        return await self.radio.transmit(channel, pdu, **kwargs)

    async def receive_response(
        self,
        channel: int,
        transmit_end_us: int,
        phy: Phy = Phy.LE_1M,
        *,
        deadline_us: int | None = None,
    ) -> Received | None:
        """Limit address detection, not the length of an acquired response."""
        response_start = transmit_end_us + LL_IFS_US
        until_us = response_start + LL_RESPONSE_START_TOLERANCE_US + phy.address_us
        if deadline_us is not None:
            until_us = min(until_us, deadline_us)
        return await self.radio.receive(
            channel,
            until_us,
            start_us=response_start - LL_RESPONSE_START_TOLERANCE_US,
            phy=phy,
        )

    async def _advertise(self, item: Advertising) -> None:
        """Run one advertising event, then schedule T_advEvent = advInterval + advDelay
        (Core Vol 6, Part B, 4.4.2.2.1).
        """
        channel = next(
            channel
            for bit, channel in enumerate(LL_ADV_PRIMARY_CHANNELS)
            if item.channel_map & (1 << bit)
        )
        start = self.radio.earliest_start_us(channel, item.primary_phy, transmit=True)
        reservations = self.reservations()
        if reservations:
            duration = advertising_event_time_us(item)
            latest = (
                item.deadline_us - duration
                if item.deadline_us
                else (
                    start + max(reservation.interval_us for reservation in reservations)
                )
            )
            gap = first_radio_gap(reservations, start, duration, latest)
            if gap != start:
                # Defer the complete event if its reservation would collide, rather than
                # sending a primary PDU whose auxiliary exchange cannot finish.
                item.next_us = (
                    gap
                    if gap is not None
                    else (item.deadline_us or start + item.interval_us)
                )
                return
        event_start = start
        item.events += 1
        if item.extended:
            await self.extended.advertise(item)
        else:
            await advertise_legacy(self, item)
        item.next_us = max(
            event_start
            + item.interval_us
            + (0 if item.high_duty else self.random.randint(0, LL_ADV_DELAY_MAX_US)),
            self.now_us + 1,
        )

    def _pending_operations(self, sync: PeriodicSync | None, target_us: int):
        """Collect due radio activities; ended advertisers are reported here first."""
        now = self.now_us
        operations: list[PendingOperation] = []
        for connection in self.connections.values():
            # Include radio preparation in the due time. Equal-anchor connections
            # rotate by last_event_us so one connection cannot monopolize the radio.
            operations.append(
                PendingOperation(
                    connection.next_operation_us - RADIO_SWITCH_TIME_US,
                    RadioPriority.CONNECTION,
                    connection,
                    partial(self._run_connection, connection, target_us),
                    connection.last_event_us,
                )
            )
        for item in self.advertisers.values():
            # Expire exhausted sets before collecting TX work, preventing one extra
            # event when the expiry and next transmission are both due.
            if item.enabled and (
                (item.deadline_us and now >= item.deadline_us)
                or (item.max_events and item.events >= item.max_events)
            ):
                item.enabled = False
                self.listener.on_advertising_ended(
                    item,
                    (
                        ErrorCode.ADVERTISING_TIMEOUT_ERROR
                        if item.deadline_us and now >= item.deadline_us
                        else ErrorCode.LIMIT_REACHED_ERROR
                    ),
                )
            if item.enabled:
                operations.append(
                    PendingOperation(
                        item.next_us,
                        RadioPriority.ADVERTISING,
                        item,
                        partial(self._advertise, item),
                    )
                )
                if item.deadline_us:
                    operations.append(
                        PendingOperation(
                            item.deadline_us,
                            RadioPriority.EXPIRY,
                            item,
                            partial(self._expire_advertiser, item),
                        )
                    )
            if item.periodic_enabled:
                # Periodic transmission has its own lifetime and can continue
                # after the associated extended advertiser has been disabled.
                operations.append(
                    PendingOperation(
                        periodic_transmit_start_us(item),
                        RadioPriority.PERIODIC_TX,
                        item,
                        partial(self._periodic_transmit, item),
                    )
                )
        contexts = self._sync_contexts(sync)
        for context in contexts:
            if context.info is None:
                continue
            window = periodic_receive_window(context)
            operations.append(
                PendingOperation(
                    window.start_us,
                    window.priority,
                    context,
                    partial(self._periodic_receive, context),
                )
            )
        return operations, contexts

    async def _run_connection(self, connection: Connection, target_us: int) -> None:
        await connection.advance_to_us(target_us, radio_until_us=self.radio_deadline_us)

    async def _scan_until(self, scan: Scanning | Initiating, end: int) -> None:
        """Listen in the current scan window; channels rotate per window (Core Vol 6,
        Part B, 4.4.3).
        """
        now = self.now_us
        if isinstance(scan, Scanning) and scan.deadline_us and now >= scan.deadline_us:
            # A finite scan either ends or moves to the next period. Period gaps
            # keep the configuration but do not reserve receiver time.
            if not scan.period_us:
                self.scan = None
                self.listener.on_scan_timeout()
                return
            scan.start_us += scan.period_us
            scan.deadline_us = scan.start_us + scan.duration_us
            self.listener.on_scan_period()
        if scan.start_us > now:
            await self.radio.advance_to_us(min(end, scan.start_us))
            return
        windows = scan.windows or (
            ScanWindow(
                Phy.LE_1M,
                scan.interval_us,
                scan.window_us,
                isinstance(scan, Scanning) and scan.active,
            ),
        )
        window, cycle, boundary = scan_window_at(windows, now - scan.start_us)
        # End this receive slice at the PHY-window boundary, then choose the next
        # channel/PHY even when the caller provided a longer idle gap.
        end = min(end, scan.start_us + boundary)
        if isinstance(scan, Scanning):
            if window is not None:
                scan.active = window.active
            if scan.deadline_us:
                end = min(end, scan.deadline_us)
        if window is not None:
            channel = LL_ADV_PRIMARY_CHANNELS[cycle % len(LL_ADV_PRIMARY_CHANNELS)]
            with self.resource.claim():
                packet = await self.radio.receive(channel, end, phy=window.phy)
                if packet:
                    if scan is self.initiating:
                        await self._initiate(channel, packet)
                    else:
                        await self._scan_packet(channel, packet)
            return
        await self.radio.advance_to_us(end)

    async def advance_to_us(self, target_us: int) -> int:
        """Serve due radio operations and use the intervening gaps for scanning.

        Reevaluate reservations after every operation because RX or Host
        callbacks can change the active connections, advertisers and syncs.
        """
        while self.now_us < target_us:
            now = self.now_us
            for connection in list(self.connections.values()):
                connection.skip_missed_events()
            # Acquiring SyncInfo and maintaining an established sync have distinct
            # failure events; neither may stay alive just because the radio is busy.
            sync = self.sync
            if (
                sync
                and sync.info is not None
                and (
                    now >= sync.deadline_us
                    or (sync.counter - sync.info.event_counter) & LL_EVENT_COUNTER_MASK
                    >= LL_PERIODIC_SYNC_ESTABLISHMENT_EVENTS
                )
            ):
                self.sync = None
                self.listener.on_sync_established(
                    sync, ErrorCode.CONNECTION_FAILED_TO_BE_ESTABLISHED_ERROR
                )
                continue
            for handle, active in list(self.syncs.items()):
                if now >= active.deadline_us:
                    del self.syncs[handle]
                    self.listener.on_sync_lost(active)
            operations, contexts = self._pending_operations(sync, target_us)
            if operations:
                # Pick by due time, priority, then fairness. Rebuild after each
                # operation
                # because its callbacks may remove or replace the remaining contexts.
                operation = self.resource.select(operations)
                due = operation.due_us
                if due <= now + 1:
                    await self.resource.execute(operation)
                    continue
                # The PHY grants time inclusively; leave the due tick available
                # for the selected activity's preparation rather than scanning over it.
                end = min(target_us, due - 1)
            else:
                end = target_us
            for context in contexts:
                if context.info is not None:
                    end = min(end, context.deadline_us)
            scans = [scan for scan in (self.initiating, self.scan) if scan is not None]
            if self.scan is None and sync and sync.info is None:
                # Use a background scan to find SyncInfo before periodic RX can be
                # scheduled.
                # TODO: honor Host scan-enable state here (Vol 4, Part E, 7.8.67).
                scans.append(
                    Scanning(
                        sync.address,
                        LL_DEFAULT_SCAN_INTERVAL_US,
                        LL_DEFAULT_SCAN_INTERVAL_US,
                    )
                )
            scan = scans[self.scan_cursor % len(scans)] if scans else None
            # Share otherwise idle gaps between initiation and explicit scanning.
            self.scan_cursor += 1
            if scan:
                await self._scan_until(scan, end)
            else:
                await self.radio.advance_to_us(end)
        return self.now_us

    async def _expire_advertiser(self, item: Advertising) -> None:
        item.enabled = False
        self.listener.on_advertising_ended(item, ErrorCode.ADVERTISING_TIMEOUT_ERROR)
