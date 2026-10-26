# Adapted for the independent BSController package.
# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Shared-radio reservations and event arbitration, independent of HCI and runtime.

Role managers supply due events. This resource manager grants a complete radio
window and owns its deadline; event executors perform the actual exchanges.
The responsibility follows Core Vol 1, Part A, 2.1.2.3.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

from bscontroller.linklayer import (
    LL_CONN_INTERVAL_UNIT_US,
    LL_MAFS_US,
    LL_PERIODIC_INTERVAL_UNIT_US,
    PDU_ADV_EXT_PAYLOAD_SIZE_MAX,
    PDU_HEADER_SIZE,
)
from bscontroller.linklayer.connection import Connection
from bscontroller.linklayer.discovery import (
    Advertising,
    PeriodicSync,
)
from bscontroller.linklayer.extended import periodic_time_us
from bscontroller.linklayer.scheduler import (
    RadioPriority,
    RadioReservation,
)
from bscontroller.linklayer.timing import (
    LL_CONN_EVENT_GUARD_US,
    window_widening,
)
from bscontroller.radio.base import RADIO_SWITCH_TIME_US

if TYPE_CHECKING:
    from bscontroller.linklayer.link import RadioLink


def connection_window(connection: Connection) -> RadioReservation:
    """Next connection event, from its (widened) start to the guard before the next
    anchor.
    """
    return RadioReservation(
        connection.event_start_us - RADIO_SWITCH_TIME_US,
        max(
            connection.next_exchange_us(),
            (
                connection.parameters.window_size * LL_CONN_INTERVAL_UNIT_US
                if not connection.established
                else 0
            ),
        )
        + LL_CONN_EVENT_GUARD_US
        + RADIO_SWITCH_TIME_US,
        connection.parameters.interval * LL_CONN_INTERVAL_UNIT_US,
    )


def periodic_transmit_start_us(item: Advertising) -> int:
    """Radio preparation start for the next AUX_SYNC_IND train."""
    return item.periodic_next_us - RADIO_SWITCH_TIME_US


def periodic_transmit_window(item: Advertising) -> RadioReservation:
    """Next AUX_SYNC_IND train, including AUX_CHAIN_IND fragments and T_MAFS.

    The duration re-encodes the train; dispatch uses periodic_transmit_start_us.
    """
    return RadioReservation(
        periodic_transmit_start_us(item),
        periodic_time_us(item) + LL_MAFS_US + RADIO_SWITCH_TIME_US,
        item.periodic_interval * LL_PERIODIC_INTERVAL_UNIT_US,
        RadioPriority.PERIODIC_TX,
    )


def periodic_receive_window(sync: PeriodicSync) -> RadioReservation:
    """Next synchronized receive window, widened on both sides (Core Vol 6, Part B,
    4.2.4).
    """
    assert sync.info is not None
    widening = window_widening(sync.next_us - sync.last_rx_us, sync.info.sca)
    return RadioReservation(
        sync.next_us - widening - RADIO_SWITCH_TIME_US,
        2 * widening
        + sync.phy.airtime_us(PDU_HEADER_SIZE + PDU_ADV_EXT_PAYLOAD_SIZE_MAX)
        + RADIO_SWITCH_TIME_US,
        sync.info.interval * LL_PERIODIC_INTERVAL_UNIT_US * sync.event_step,
        RadioPriority.PERIODIC_RX,
    )


@dataclass(frozen=True)
class PendingOperation:
    """One due radio activity; run() performs it on the owning link."""

    due_us: int
    priority: RadioPriority
    owner: Connection | Advertising | PeriodicSync
    run: Callable[[], Awaitable[object]]
    # Equal-time connections rotate by their last served event.
    order: int = 0


class RadioResourceManager:
    def __init__(self, link: RadioLink):
        self.link = link
        self.deadline_us: int | None = None

    @staticmethod
    def select(operations: list[PendingOperation]) -> PendingOperation:
        """Earliest due event, then radio priority and per-role fairness."""
        return min(
            operations, key=lambda entry: (entry.due_us, entry.priority, entry.order)
        )

    @contextmanager
    def claim(self, owner: object = None):
        """Bound an event's work by the next competing reservation; release on all
        exits.
        """
        previous = self.deadline_us
        self.deadline_us = self.radio_limit(owner)
        try:
            yield self.deadline_us
        finally:
            self.deadline_us = previous

    async def execute(self, operation: PendingOperation) -> None:
        with self.claim(operation.owner):
            await operation.run()

    def reservations(self, *, exclude: object = None) -> list[RadioReservation]:
        """Every periodic activity's next window, other than exclude's."""
        result = [
            connection_window(connection)
            for connection in self.link.connections.values()
            if connection is not exclude
        ]
        result += [
            periodic_transmit_window(item)
            for item in self.link.advertisers.values()
            if item is not exclude and item.periodic_enabled
        ]
        result += [
            periodic_receive_window(sync)
            for sync in self.link._sync_contexts(self.link.sync)
            if sync is not exclude and sync.info is not None
        ]
        return result

    def radio_limit(self, owner: object = None) -> int | None:
        starts = [
            start
            for reservation in self.reservations(exclude=owner)
            for start, _ in [reservation.window_after(self.link.now_us + 1)]
            if start > self.link.now_us + 1
        ]
        return min(starts) if starts else None

    def fits_radio(self, end_us: int) -> bool:
        return self.deadline_us is None or end_us <= self.deadline_us
