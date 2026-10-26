# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Controller-side LL service boundary, independent of HCI packets and transport.

HCI supplies decoded configuration and converts returned Controller error codes
into responses. This boundary validates configuration and delegates lifetime
changes to LL role owners; RadioLink drives their prepared activities. Queries
return detached values. See Core Vol 1, Part A, 2.1.2.1-2.1.2.3.
"""

from __future__ import annotations

from dataclasses import fields, replace
from typing import TYPE_CHECKING

from bscontroller.capabilities import (
    CONTROLLER_ADVERTISING_SET_COUNT,
    CONTROLLER_CONNECTION_COUNT,
    CONTROLLER_PERIODIC_SYNC_COUNT,
    CONTROLLER_SUPPORTED_PHY_MASK,
)
from bscontroller.errors import ErrorCode
from bscontroller.linklayer import (
    LL_ADV_DIRECT_HIGH_DUTY_TIMEOUT_US,
    LL_DATA_CHANNEL_MAP_ALL,
    LL_MAFS_US,
    LL_PERIODIC_INTERVAL_UNIT_US,
    PDU_ADV_ADI_DID_MASK,
    PDU_ADV_LEGACY_DATA_SIZE_MAX,
    AdvertisingMode,
)
from bscontroller.linklayer.api import (
    AddressSnapshot,
    AdvertisingConfig,
    AdvertisingSnapshot,
    ConnectionSnapshot,
    InitiatingConfig,
    PeriodicSyncConfig,
    PeriodicSyncSnapshot,
    ScanBackoffSnapshot,
    ScanningSnapshot,
    ScanWindowConfig,
    advertising_snapshot,
    connection_snapshot,
    synchronization_snapshot,
)
from bscontroller.linklayer.discovery import (
    Advertising,
    Initiating,
    PeriodicSync,
    ScanBackoff,
    Scanning,
    ScanWindow,
)
from bscontroller.linklayer.extended import (
    advertising_time_us,
    auxiliary_pdu,
    periodic_time_us,
)
from bscontroller.linklayer.llcp import PreparedProcedure
from bscontroller.linklayer.state import Role

if TYPE_CHECKING:
    from bscontroller.address import Address
    from bscontroller.linklayer.link import RadioLink

SUCCESS = ErrorCode.SUCCESS
INVALID = ErrorCode.INVALID_COMMAND_PARAMETERS_ERROR
DISALLOWED = ErrorCode.COMMAND_DISALLOWED_ERROR
UNKNOWN_ADV = ErrorCode.UNKNOWN_ADVERTISING_IDENTIFIER_ERROR
TOO_LONG = ErrorCode.PACKET_TOO_LONG_ERROR


class AdvertisingService:
    """Configure and publish advertisers; HCI fragment staging remains above this
    API.
    """

    def __init__(self, link: RadioLink):
        self.link = link

    def snapshot(self, handle: int) -> AdvertisingSnapshot | None:
        item = self.link.advertisers.get(handle)
        return advertising_snapshot(handle, item) if item is not None else None

    def any_enabled(self) -> bool:
        return any(item.enabled for item in self.link.advertisers.values())

    def has_extended_sets(self) -> bool:
        return any(handle != -1 for handle in self.link.advertisers)

    def _candidate(self, handle: int, config: AdvertisingConfig) -> Advertising:
        if not isinstance(config, AdvertisingConfig):
            raise TypeError('advertising configuration must not contain live state')
        original = self.link.advertisers.get(handle)
        values = {field.name: getattr(config, field.name) for field in fields(config)}
        if original is None:
            return Advertising(**values)
        if original.random_address is not None and config.address.is_random:
            values['address'] = original.random_address
        # Keep counters, deadlines, periodic identity and payloads in LL. Upper
        # layers replace only configuration, never a running context.
        return replace(
            original,
            **values,
            data=bytes(original.data),
            scan_response=bytes(original.scan_response),
            periodic_data=bytes(original.periodic_data),
        )

    def configure_legacy(self, config: AdvertisingConfig) -> None:
        candidate = self._candidate(-1, config)
        current = self.link.advertisers.get(-1)
        if current is None:
            self.link.roles.advertising.publish(-1, candidate)
        else:
            # Data commands may run during a radio await. Keep the context held
            # by that event executor; only LL applies the decoded configuration.
            for field in fields(config):
                setattr(current, field.name, getattr(candidate, field.name))

    def configuration_status(self, handle: int, incompatible_periodic: bool) -> int:
        item = self.link.advertisers.get(handle)
        if item and item.periodic_enabled and incompatible_periodic:
            return INVALID
        if item and (item.enabled or item.periodic_enabled):
            return DISALLOWED
        if (
            item is None
            and len(self.link.advertisers) >= CONTROLLER_ADVERTISING_SET_COUNT
        ):
            return ErrorCode.MEMORY_CAPACITY_EXCEEDED_ERROR
        return SUCCESS

    def configure(self, handle: int, config: AdvertisingConfig) -> int:
        item = self._candidate(handle, config)
        status = self.configuration_status(
            handle, not item.extended or bool(item.mode) or item.anonymous
        )
        if status == SUCCESS:
            status = self.data_status(item)
        if status == SUCCESS:
            self.link.roles.advertising.publish(handle, item)
        return status

    @staticmethod
    def data_status(item: Advertising) -> int:
        """Validate payload placement and complete-event airtime before a configuration
        commit.
        """
        if (
            (
                not item.extended
                and (
                    len(item.data) > PDU_ADV_LEGACY_DATA_SIZE_MAX
                    or len(item.scan_response) > PDU_ADV_LEGACY_DATA_SIZE_MAX
                )
            )
            or (item.target is not None and not item.extended and item.data)
            or (item.extended and item.mode == AdvertisingMode.SCANNABLE and item.data)
            or (
                item.extended
                and item.mode != AdvertisingMode.SCANNABLE
                and item.scan_response
            )
        ):
            return INVALID
        if (
            item.extended
            and item.mode == AdvertisingMode.CONNECTABLE
            and len(item.data) > auxiliary_pdu(item).data_capacity()
        ) or advertising_time_us(item) > item.interval_max_us:
            return TOO_LONG
        return SUCCESS

    def set_random_address(self, handle: int, address: Address) -> int:
        item = self.link.advertisers.get(handle)
        if item is None:
            return UNKNOWN_ADV
        if item.enabled:
            return DISALLOWED
        address = AddressSnapshot(address)
        item.random_address = address
        if item.address.is_random:
            item.address = address
        return SUCCESS

    def store_data(
        self, handle: int, field: str, data: bytes, *, renew: bool = False
    ) -> None:
        """Commit only the selected payload; a completed HCI sequence renews its
        identity once.
        """
        if field not in ('data', 'scan_response', 'periodic_data'):
            raise ValueError('unknown advertising payload')
        item = self.link.advertisers[handle]
        setattr(item, field, bytearray(data))
        if renew:
            self.renew_data_identity(handle)

    def renew_data_identity(self, handle: int) -> None:
        # Preserve existing DID policy here; it is independent of HCI assembly.
        # TODO: separate random DIDs (Core Vol 6, Part B, 4.4.2.11).
        item = self.link.advertisers[handle]
        item.did = (item.did + 1) & PDU_ADV_ADI_DID_MASK

    def validate_data(self, handle: int, field: str, value: bytes) -> int:
        item = self.link.advertisers[handle]
        updated = replace(item, **{field: value})
        if (
            (
                item.extended
                and item.mode == AdvertisingMode.CONNECTABLE
                and field == 'data'
                and len(value) > auxiliary_pdu(item).data_capacity()
            )
            or (
                field == 'periodic_data'
                and item.periodic_interval
                and periodic_time_us(updated) + LL_MAFS_US
                >= item.periodic_interval * LL_PERIODIC_INTERVAL_UNIT_US
            )
            or advertising_time_us(updated)
            > (item.interval_us if item.enabled else item.interval_max_us)
        ):
            return TOO_LONG
        return SUCCESS

    def publication_status(self, handle: int, field: str, value: bytes) -> int:
        item = self.link.advertisers[handle]
        candidate = replace(item, **{field: value})
        if (
            item.periodic_enabled
            and advertising_time_us(candidate)
            + periodic_time_us(candidate)
            + LL_MAFS_US
            >= item.periodic_interval * LL_PERIODIC_INTERVAL_UNIT_US
        ):
            return DISALLOWED
        return SUCCESS

    def enable_legacy(self, enable: bool) -> int:
        item = self.link.advertisers[-1]
        item.enabled = enable
        item.next_us = self.link.now_us + 1
        item.events = 0
        item.deadline_us = (
            self.link.now_us + LL_ADV_DIRECT_HIGH_DUTY_TIMEOUT_US
            if item.high_duty
            else 0
        )
        return SUCCESS

    def enable(
        self,
        enable: bool,
        sets: tuple[tuple[int, int, int], ...],
        *,
        interval_unit_us: int,
    ) -> int:
        """Preflight the entire request before committing any set (Vol 4, Part E,
        7.8.56).
        """
        handles = [handle for handle, _, _ in sets]
        if any(handle not in self.link.advertisers for handle in handles):
            return UNKNOWN_ADV
        if enable:
            for handle in handles:
                item = self.link.advertisers[handle]
                if (
                    item.extended
                    and item.mode == AdvertisingMode.SCANNABLE
                    and not item.scan_response
                ):
                    return DISALLOWED
                if advertising_time_us(item) > item.interval_max_us:
                    return TOO_LONG
        selected = sets or tuple((handle, 0, 0) for handle in self.link.advertisers)
        for handle, duration, max_events in selected:
            item = self.link.advertisers[handle]
            if enable:
                airtime = advertising_time_us(item)
                item.interval_us = max(
                    item.interval_us,
                    (airtime + interval_unit_us - 1)
                    // interval_unit_us
                    * interval_unit_us,
                )
            item.enabled = enable
            item.next_us = self.link.now_us + 1
            item.events = 0
            item.max_events = max_events
            if item.high_duty:
                # TODO: reject invalid high-duty Duration instead of clamping (7.8.56).
                duration = min(
                    duration or LL_ADV_DIRECT_HIGH_DUTY_TIMEOUT_US,
                    LL_ADV_DIRECT_HIGH_DUTY_TIMEOUT_US,
                )
            item.deadline_us = self.link.now_us + duration if duration else 0
        return SUCCESS

    def remove(self, handle: int) -> int:
        item = self.link.advertisers.get(handle)
        if item is None:
            return UNKNOWN_ADV
        if item.enabled or item.periodic_enabled:
            return DISALLOWED
        self.link.roles.advertising.remove(handle)
        return SUCCESS

    def clear(self) -> int:
        if any(
            item.enabled or item.periodic_enabled
            for item in self.link.advertisers.values()
        ):
            return DISALLOWED
        self.link.roles.advertising.clear()
        return SUCCESS

    def set_periodic_interval(self, handle: int, minimum: int, maximum: int) -> int:
        item = self.link.advertisers[handle]
        if item.periodic_enabled:
            return DISALLOWED
        if not item.extended or item.mode or item.anonymous:
            return INVALID
        if (
            periodic_time_us(item) + LL_MAFS_US
            >= maximum * LL_PERIODIC_INTERVAL_UNIT_US
        ):
            return TOO_LONG
        item.periodic_interval = minimum
        return SUCCESS

    def enable_periodic(self, handle: int, enable: bool) -> int:
        item = self.link.advertisers[handle]
        if (
            not item.extended
            or not item.periodic_interval
            or item.mode
            or item.anonymous
        ):
            return DISALLOWED
        if (
            enable
            and periodic_time_us(item) + LL_MAFS_US
            >= item.periodic_interval * LL_PERIODIC_INTERVAL_UNIT_US
        ):
            return TOO_LONG
        if (
            enable
            and advertising_time_us(replace(item, periodic_enabled=True))
            + periodic_time_us(item)
            + LL_MAFS_US
            >= item.periodic_interval * LL_PERIODIC_INTERVAL_UNIT_US
        ):
            return DISALLOWED
        self.link.roles.advertising.set_periodic_enabled(item, enable)
        return SUCCESS


class LinkLayerService:
    """LL control operations; live state is committed here before upper-layer
    notification.
    """

    def __init__(
        self,
        link: RadioLink,
        address: Address,
        scan_interval_us: int,
        scan_window_us: int,
    ):
        self.link = link
        self.advertising = AdvertisingService(link)
        self._default_scan = (scan_interval_us, scan_window_us)
        self.reset_configuration(address)

    def reset_configuration(self, address: Address) -> None:
        self._scan_parameters = Scanning(AddressSnapshot(address), *self._default_scan)
        self.host_channel_map = LL_DATA_CHANNEL_MAP_ALL
        self.link.default_tx_phys = self.link.default_rx_phys = (
            CONTROLLER_SUPPORTED_PHY_MASK
        )

    @property
    def scan_parameters(self) -> ScanningSnapshot:
        scan = self._scan_parameters
        return ScanningSnapshot(
            AddressSnapshot(scan.address),
            scan.interval_us,
            scan.window_us,
            scan.active,
            scan.start_us,
            tuple(
                ScanWindowConfig(
                    window.phy, window.interval_us, window.window_us, window.active
                )
                for window in scan.windows
            ),
            scan.duration_us,
            scan.period_us,
            scan.deadline_us,
            scan.filter_policy,
            ScanBackoffSnapshot(
                scan.backoff.count,
                scan.backoff.upper_limit,
                scan.backoff.successes,
                scan.backoff.failures,
            ),
        )

    def configure_scanning(
        self,
        address: Address,
        interval_us: int,
        window_us: int,
        active: bool,
        policy: int,
    ) -> int:
        if self.link.scan is not None:
            return DISALLOWED
        self._scan_parameters = Scanning(
            AddressSnapshot(address),
            interval_us,
            window_us,
            active,
            filter_policy=policy,
        )
        return SUCCESS

    def configure_scan_windows(self, windows: tuple[ScanWindowConfig, ...]) -> None:
        self._scan_parameters.windows = tuple(
            ScanWindow(item.phy, item.interval_us, item.window_us, item.active)
            for item in windows
        )

    def enable_scanning(self, enable: bool) -> None:
        scan = self._scan_parameters
        scan.start_us = self.link.now_us
        scan.backoff = ScanBackoff()
        self.link.roles.scanning.enable(scan if enable else None)

    def set_scan_period(self, duration_us: int, period_us: int) -> None:
        scan = self._scan_parameters
        scan.duration_us, scan.period_us = duration_us, period_us
        scan.deadline_us = self.link.now_us + duration_us if duration_us else 0

    def initiating_status(self, peer: Address, use_list: bool) -> int:
        if not use_list and any(
            connection.peer == peer for connection in self.link.connections.values()
        ):
            return ErrorCode.CONNECTION_ALREADY_EXISTS_ERROR
        if self.link.initiating is not None:
            return DISALLOWED
        if len(self.link.connections) >= CONTROLLER_CONNECTION_COUNT:
            return ErrorCode.CONNECTION_LIMIT_EXCEEDED_ERROR
        return SUCCESS

    def start_initiating(self, config: InitiatingConfig) -> int:
        status = self.initiating_status(config.peer, bool(config.filter_policy))
        if status == SUCCESS:
            windows = tuple(
                ScanWindow(item.phy, item.interval_us, item.window_us, item.active)
                for item in config.windows
            )
            parameters = dict(config.phy_parameters)
            first = windows[0]
            item = Initiating(
                config.address,
                config.peer,
                first.interval_us,
                first.window_us,
                next(iter(parameters.values())),
                self.link.now_us,
                windows=windows,
                phy_parameters=parameters,
                filter_policy=config.filter_policy,
            )
            self.link.roles.scanning.start_initiating(item)
        return status

    def cancel_initiating(self) -> Address | None:
        item = self.link.roles.scanning.cancel_initiating()
        return AddressSnapshot(item.peer) if item is not None else None

    def synchronization_status(self, address: Address, sid: int, use_list: bool) -> int:
        if self.link.sync is not None:
            return DISALLOWED
        if not use_list and any(
            active.address == address and active.sid == sid
            for active in self.link.syncs.values()
        ):
            return ErrorCode.CONNECTION_ALREADY_EXISTS_ERROR
        if len(self.link.syncs) >= CONTROLLER_PERIODIC_SYNC_COUNT:
            return ErrorCode.MEMORY_CAPACITY_EXCEEDED_ERROR
        return SUCCESS

    def start_synchronizing(self, config: PeriodicSyncConfig) -> int:
        status = self.synchronization_status(
            config.address, config.sid, config.use_list
        )
        if status != SUCCESS:
            return status
        sync = PeriodicSync(
            config.address,
            config.sid,
            config.timeout_us,
            0,
            config.skip,
            config.reports_enabled,
            use_list=config.use_list,
        )
        self.link.roles.synchronization.start(sync)
        return SUCCESS

    def cancel_synchronizing(self) -> PeriodicSyncSnapshot | None:
        sync = self.link.sync
        if sync is None or sync.established:
            return None
        self.link.roles.synchronization.cancel()
        return synchronization_snapshot(sync)

    def terminate_synchronization(self, handle: int) -> int:
        if handle not in self.link.syncs:
            return ErrorCode.UNKNOWN_CONNECTION_IDENTIFIER_ERROR
        self.link.roles.synchronization.terminate(handle)
        return SUCCESS

    def has_synchronization(self, handle: int) -> bool:
        return handle in self.link.syncs

    def enable_periodic_reports(self, handle: int, enabled: bool) -> None:
        self.link.roles.synchronization.enable_reports(handle, enabled)

    @property
    def scanning_enabled(self) -> bool:
        return self.link.scan is not None

    @property
    def initiating_enabled(self) -> bool:
        return self.link.initiating is not None

    @property
    def synchronizing(self) -> bool:
        return self.link.sync is not None

    def filter_in_use(self) -> bool:
        return (
            any(
                item.enabled and item.filter_policy
                for item in self.link.advertisers.values()
            )
            or bool(self.link.scan and self.link.scan.filter_policy)
            or bool(self.link.initiating and self.link.initiating.filter_policy)
        )

    @property
    def now_us(self) -> int:
        return self.link.now_us

    def random_bytes(self, length: int) -> bytes:
        return self.link.random.randbytes(length)

    def default_data_length(self) -> tuple[int, int]:
        return self.link.default_tx_octets, self.link.default_tx_time

    def reset(self, address: Address) -> None:
        self.link.reset()
        self.reset_configuration(address)

    def edit_filter(self, address: Address | None, add: bool, capacity: int) -> int:
        if self.filter_in_use():
            return DISALLOWED
        items = self.link.accept_list
        if address is None:
            items.clear()
        elif add:
            if address not in items and len(items) >= capacity:
                return ErrorCode.MEMORY_CAPACITY_EXCEEDED_ERROR
            items.add(AddressSnapshot(address))
        else:
            items.discard(address)
        return SUCCESS

    def edit_periodic_list(
        self, key: tuple[Address, int] | None, add: bool, capacity: int
    ) -> int:
        if self.link.sync is not None:
            return DISALLOWED
        items = self.link.periodic_advertiser_list
        if key is None:
            items.clear()
        elif add:
            if key in items:
                return INVALID
            if len(items) >= capacity:
                return ErrorCode.MEMORY_CAPACITY_EXCEEDED_ERROR
            items.add((AddressSnapshot(key[0]), key[1]))
        else:
            if key not in items:
                return UNKNOWN_ADV
            items.remove(key)
        return SUCCESS

    def set_default_phys(self, tx: int, rx: int) -> None:
        self.link.default_tx_phys, self.link.default_rx_phys = tx, rx

    def classify_channels(self, value: int) -> int:
        centrals = [
            connection
            for connection in self.link.connections.values()
            if connection.role == Role.CENTRAL
        ]
        if any(connection.controls.busy for connection in centrals):
            return DISALLOWED
        for connection in centrals:
            connection.controls.request_channel_map(value)
        self.host_channel_map = value
        return SUCCESS

    def set_default_data_length(self, octets: int, time_us: int) -> None:
        self.link.default_tx_octets, self.link.default_tx_time = octets, time_us

    def _connection(self, handle: int):
        connection = self.link.connections.get(handle)
        return connection if connection and connection.reported else None

    def connection_snapshot(self, handle: int) -> ConnectionSnapshot | None:
        connection = self._connection(handle)
        return connection_snapshot(connection) if connection is not None else None

    def prepare_encryption(
        self, handle: int, rand: bytes, ediv: int, key: bytes
    ) -> PreparedProcedure:
        connection = self._connection(handle)
        return (
            connection.llcp.prepare_encryption(rand, ediv, key)
            if connection
            else PreparedProcedure(ErrorCode.UNKNOWN_CONNECTION_IDENTIFIER_ERROR)
        )

    def prepare_features(self, handle: int) -> PreparedProcedure:
        connection = self._connection(handle)
        return (
            connection.llcp.prepare_features()
            if connection
            else PreparedProcedure(ErrorCode.UNKNOWN_CONNECTION_IDENTIFIER_ERROR)
        )

    def prepare_version(self, handle: int) -> PreparedProcedure:
        connection = self._connection(handle)
        return (
            connection.llcp.prepare_version()
            if connection
            else PreparedProcedure(ErrorCode.UNKNOWN_CONNECTION_IDENTIFIER_ERROR)
        )

    def prepare_phy(
        self, handle: int, tx: int, rx: int, coding: int, parameter_status: int
    ) -> PreparedProcedure:
        connection = self._connection(handle)
        return (
            connection.llcp.prepare_phy(tx, rx, coding, parameter_status)
            if connection
            else PreparedProcedure(ErrorCode.UNKNOWN_CONNECTION_IDENTIFIER_ERROR)
        )

    def prepare_parameters(
        self,
        handle: int,
        minimum: int,
        maximum: int,
        latency: int,
        timeout: int,
        *,
        valid_ce_lengths: bool,
    ) -> PreparedProcedure:
        connection = self._connection(handle)
        return (
            connection.llcp.prepare_parameters(
                minimum, maximum, latency, timeout, valid_ce_lengths=valid_ce_lengths
            )
            if connection
            else PreparedProcedure(ErrorCode.UNKNOWN_CONNECTION_IDENTIFIER_ERROR)
        )

    def supply_key(self, handle: int, key: bytes | None) -> int:
        connection = self._connection(handle)
        return (
            connection.llcp.supply_key(key)
            if connection
            else ErrorCode.UNKNOWN_CONNECTION_IDENTIFIER_ERROR
        )

    def reply_parameters(
        self, handle: int, minimum: int, maximum: int, latency: int, timeout: int
    ) -> int:
        connection = self._connection(handle)
        return (
            connection.llcp.reply_parameters(minimum, maximum, latency, timeout)
            if connection
            else ErrorCode.UNKNOWN_CONNECTION_IDENTIFIER_ERROR
        )

    def reject_parameters(self, handle: int, reason: int) -> int:
        connection = self._connection(handle)
        return (
            connection.llcp.reject_parameters(reason)
            if connection
            else ErrorCode.UNKNOWN_CONNECTION_IDENTIFIER_ERROR
        )

    def set_data_length(self, handle: int, octets: int, time_us: int) -> int:
        connection = self._connection(handle)
        return (
            connection.llcp.set_data_length(octets, time_us)
            if connection
            else ErrorCode.UNKNOWN_CONNECTION_IDENTIFIER_ERROR
        )

    def set_authenticated_timeout(self, handle: int, timeout_us: int) -> int:
        connection = self._connection(handle)
        if connection is None:
            return ErrorCode.UNKNOWN_CONNECTION_IDENTIFIER_ERROR
        if not timeout_us:
            return INVALID
        connection.encryption.auth_timeout_us = timeout_us
        return SUCCESS

    def disconnect(self, handle: int, reason: int) -> int:
        connection = self._connection(handle)
        if connection is None:
            return ErrorCode.UNKNOWN_CONNECTION_IDENTIFIER_ERROR
        connection.terminate(reason)
        return SUCCESS

    def send_acl(self, handle: int, continuation: bool, data: bytes) -> None:
        connection = self._connection(handle)
        if connection is not None:
            connection.enqueue_acl(continuation, data)
