# Adapted for the independent BSController package.
# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Scanning, filtering and periodic synchronization HCI commands."""

import asyncio

from bscontroller import hci
from bscontroller.capabilities import (
    CONTROLLER_PERIODIC_ADVERTISER_LIST_SIZE,
    CONTROLLER_PRIMARY_SCAN_PHY_MASK,
)
from bscontroller.hci import (
    HCI_LE_DURATION_UNIT_US,
    HCI_LE_EXT_SCAN_INTERVAL_MAX,
    HCI_LE_PERIODIC_SYNC_REPORTS_DISABLED_MASK,
    HCI_LE_PERIODIC_SYNC_SKIP_MAX,
    HCI_LE_PERIODIC_SYNC_TIMEOUT_MAX,
    HCI_LE_PERIODIC_SYNC_TIMEOUT_MIN,
    HCI_LE_SCAN_DUPLICATES_DISABLED,
    HCI_LE_SCAN_DUPLICATES_ENABLED,
    HCI_LE_SCAN_DUPLICATES_RESET_EACH_PERIOD,
    HCI_LE_SCAN_INTERVAL_MAX,
    HCI_LE_SCAN_INTERVAL_MIN,
    HCI_LE_SCAN_INTERVAL_UNIT_US,
    HCI_LE_SCAN_PERIOD_UNIT_US,
)
from bscontroller.hci.context import (
    DISALLOWED,
    INVALID,
    SUCCESS,
    UNSUPPORTED,
    LeControllerContext,
)
from bscontroller.linklayer import PDU_ADV_ADDRESS_SIZE, PDU_ADV_ADI_SID_MAX
from bscontroller.linklayer.discovery import (
    PeriodicSync,
    ScanWindow,
)
from bscontroller.radio.base import Phy

SyncOptions = hci.HCI_LE_Periodic_Advertising_Create_Sync_Command.Options


class LeScanningCommands(LeControllerContext):
    def _scan_parameters(
        self,
        own,
        policy,
        scan_type,
        interval,
        window,
        maximum_interval=HCI_LE_SCAN_INTERVAL_MAX,
    ):
        """Validate and replace the saved scan configuration in scheduler units.

        See Bluetooth Core 6.3, Vol 4, Part E, 7.8.10 and 7.8.64.
        """
        if self.link.scan:
            return hci.HCI_StatusReturnParameters(DISALLOWED)
        if scan_type not in (0, 1):
            return hci.HCI_StatusReturnParameters(INVALID)
        if own not in (
            hci.OwnAddressType.PUBLIC,
            hci.OwnAddressType.RANDOM,
        ) or policy not in (0, 1):
            return hci.HCI_StatusReturnParameters(UNSUPPORTED)
        if not HCI_LE_SCAN_INTERVAL_MIN <= window <= interval <= maximum_interval:
            return hci.HCI_StatusReturnParameters(INVALID)
        # Replace the saved configuration only after validation, converting
        # HCI's 0.625-ms interval/window units to scheduler microseconds.
        status = self.ll.configure_scanning(
            self._address(own),
            interval * HCI_LE_SCAN_INTERVAL_UNIT_US,
            window * HCI_LE_SCAN_INTERVAL_UNIT_US,
            bool(scan_type),
            policy,
        )
        return hci.HCI_StatusReturnParameters(status)

    def on_hci_le_set_scan_parameters_command(self, command):
        '''
        See Bluetooth spec Vol 4, Part E - 7.8.10 LE Set Scan Parameters Command
        '''
        result = self._scan_parameters(
            command.own_address_type,
            command.scanning_filter_policy,
            command.le_scan_type,
            command.le_scan_interval,
            command.le_scan_window,
        )
        if result.status == SUCCESS:
            self.extended_scan = False
        return result

    def on_hci_le_set_extended_scan_parameters_command(self, command):
        '''
        See Bluetooth spec Vol 4, Part E - 7.8.64 LE Set Extended Scan Parameters
        Command
        '''
        if not command.scanning_phys:
            return hci.HCI_StatusReturnParameters(INVALID)
        if command.scanning_phys & ~CONTROLLER_PRIMARY_SCAN_PHY_MASK:
            return hci.HCI_StatusReturnParameters(UNSUPPORTED)
        # HCI arrays are packed in increasing PHY-bit order, with no entry for
        # an unset bit. LE 2M cannot scan primary advertising channels.
        phys = [
            phy
            for phy, bit in (
                (Phy.LE_1M, hci.PhyBit.LE_1M),
                (Phy.LE_CODED, hci.PhyBit.LE_CODED),
            )
            if command.scanning_phys & bit
        ]
        if (
            not len(phys)
            == len(command.scan_types)
            == len(command.scan_intervals)
            == len(command.scan_windows)
        ):
            return hci.HCI_StatusReturnParameters(INVALID)
        if any(
            kind not in (0, 1)
            or not HCI_LE_SCAN_INTERVAL_MIN
            <= window
            <= interval
            <= HCI_LE_EXT_SCAN_INTERVAL_MAX
            for kind, interval, window in zip(
                command.scan_types, command.scan_intervals, command.scan_windows
            )
        ):
            return hci.HCI_StatusReturnParameters(INVALID)
        # Validate all PHY entries before _scan_parameters replaces the live
        # configuration; a bad later entry must not commit the first one.
        result = self._scan_parameters(
            command.own_address_type,
            command.scanning_filter_policy,
            command.scan_types[0],
            command.scan_intervals[0],
            command.scan_windows[0],
            maximum_interval=HCI_LE_EXT_SCAN_INTERVAL_MAX,
        )
        if result.status == SUCCESS:
            self.extended_scan = True
            self.ll.configure_scan_windows(
                tuple(
                    ScanWindow(
                        phy,
                        interval * HCI_LE_SCAN_INTERVAL_UNIT_US,
                        window * HCI_LE_SCAN_INTERVAL_UNIT_US,
                        bool(kind),
                    )
                    for phy, kind, interval, window in zip(
                        phys,
                        command.scan_types,
                        command.scan_intervals,
                        command.scan_windows,
                    )
                )
            )
        return result

    def _scan_enable(self, enable, duplicates):
        """Shared checks for LE Set (Extended) Scan Enable (Vol 4, Part E, 7.8.11,
        7.8.65).
        """
        if enable not in (0, 1) or duplicates not in (
            HCI_LE_SCAN_DUPLICATES_DISABLED,
            HCI_LE_SCAN_DUPLICATES_ENABLED,
            HCI_LE_SCAN_DUPLICATES_RESET_EACH_PERIOD,
        ):
            return hci.HCI_StatusReturnParameters(INVALID)
        self.filter_duplicates = bool(duplicates)
        # Start a new scan epoch with fresh duplicate-filter and backoff history.
        # The backoff follows the example in Vol 6, Part B, 4.4.3.2.
        self.seen.clear()
        self.ll.enable_scanning(bool(enable))
        return hci.HCI_StatusReturnParameters(SUCCESS)

    def on_hci_le_set_scan_enable_command(self, command):
        '''
        See Bluetooth spec Vol 4, Part E - 7.8.11 LE Set Scan Enable Command
        '''
        if command.filter_duplicates not in (0, 1):
            return hci.HCI_StatusReturnParameters(INVALID)
        return self._scan_enable(command.le_scan_enable, command.filter_duplicates)

    def on_hci_le_set_extended_scan_enable_command(self, command):
        '''
        See Bluetooth spec Vol 4, Part E - 7.8.65 LE Set Extended Scan Enable Command
        '''
        if (
            command.duration
            and command.period
            and command.duration * HCI_LE_DURATION_UNIT_US
            >= command.period * HCI_LE_SCAN_PERIOD_UNIT_US
        ):
            return hci.HCI_StatusReturnParameters(INVALID)
        result = self._scan_enable(command.enable, command.filter_duplicates)
        if result.status == SUCCESS:
            self.ll.set_scan_period(
                command.duration * HCI_LE_DURATION_UNIT_US,
                command.period * HCI_LE_SCAN_PERIOD_UNIT_US,
            )
            self.period_duplicate_reset = (
                command.filter_duplicates == HCI_LE_SCAN_DUPLICATES_RESET_EACH_PERIOD
            )
        return result

    def _filter_in_use(self):
        return (
            any(
                item.enabled and item.filter_policy
                for item in self.link.advertisers.values()
            )
            or bool(self.link.scan and self.link.scan.filter_policy)
            or bool(self.link.initiating and self.link.initiating.filter_policy)
        )

    def on_hci_le_read_filter_accept_list_size_command(self, command):
        '''
        See Bluetooth spec Vol 4, Part E - 7.8.14 LE Read Filter Accept List Size
        Command
        '''
        return hci.HCI_LE_Read_Filter_Accept_List_Size_ReturnParameters(
            SUCCESS, self.controller.filter_accept_list_size
        )

    def on_hci_le_clear_filter_accept_list_command(self, command):
        return hci.HCI_StatusReturnParameters(
            self.ll.edit_filter(None, False, self.controller.filter_accept_list_size)
        )

    def _edit_filter(self, command, add):
        """Filter Accept List edits, disallowed while the list is in use (Vol 4, Part E,
        7.8.16, 7.8.17).
        """
        if self._filter_in_use():
            return hci.HCI_StatusReturnParameters(DISALLOWED)
        if command.address_type not in (
            hci.AddressType.PUBLIC_DEVICE,
            hci.AddressType.RANDOM_DEVICE,
            hci.AddressType.ANONYMOUS,
        ):
            return hci.HCI_StatusReturnParameters(INVALID)
        address = hci.Address(
            (
                bytes(PDU_ADV_ADDRESS_SIZE)
                if command.address_type == hci.AddressType.ANONYMOUS
                else bytes(command.address)
            ),
            command.address_type,
        )
        return hci.HCI_StatusReturnParameters(
            self.ll.edit_filter(address, add, self.controller.filter_accept_list_size)
        )

    def on_hci_le_add_device_to_filter_accept_list_command(self, command):
        '''
        See Bluetooth spec Vol 4, Part E - 7.8.16 LE Add Device To Filter Accept List
        Command
        '''
        return self._edit_filter(command, True)

    def on_hci_le_remove_device_from_filter_accept_list_command(self, command):
        '''
        See Bluetooth spec Vol 4, Part E - 7.8.17 LE Remove Device From Filter Accept
        List Command
        '''
        return self._edit_filter(command, False)

    def on_hci_le_periodic_advertising_create_sync_command(self, command):
        '''
        See Bluetooth spec Vol 4, Part E - 7.8.67 LE Periodic Advertising Create Sync
        Command
        '''
        use_list = bool(command.options & SyncOptions.USE_PERIODIC_ADVERTISER_LIST)
        status = self.ll.synchronization_status(
            hci.Address(
                bytes(command.advertiser_address), command.advertiser_address_type
            ),
            command.advertising_sid,
            use_list,
        )
        if status != SUCCESS:
            self.controller._send_hci_command_status(status, command.op_code)
            return
        if (
            command.options
            & ~(
                HCI_LE_PERIODIC_SYNC_REPORTS_DISABLED_MASK
                | SyncOptions.USE_PERIODIC_ADVERTISER_LIST
            )
            or command.sync_cte_type
        ):
            self.controller._send_hci_command_status(UNSUPPORTED, command.op_code)
            return
        if (
            not HCI_LE_PERIODIC_SYNC_TIMEOUT_MIN
            <= command.sync_timeout
            <= HCI_LE_PERIODIC_SYNC_TIMEOUT_MAX
            or not 0 <= command.skip <= HCI_LE_PERIODIC_SYNC_SKIP_MAX
            or (
                not command.options & SyncOptions.USE_PERIODIC_ADVERTISER_LIST
                and (
                    command.advertiser_address_type
                    not in (
                        hci.AddressType.PUBLIC_DEVICE,
                        hci.AddressType.RANDOM_DEVICE,
                    )
                    or not 0 <= command.advertising_sid <= PDU_ADV_ADI_SID_MAX
                )
            )
        ):
            self.controller._send_hci_command_status(INVALID, command.op_code)
            return
        # Reserve a free handle for acquisition; publish it as an established
        # sync only after receiving the periodic train.
        status = self.ll.start_synchronizing(
            PeriodicSync(
                command.advertiser_address,
                command.advertising_sid,
                command.sync_timeout * hci.HCI_LE_PERIODIC_SYNC_TIMEOUT_UNIT_US,
                0,
                command.skip,
                not command.options & HCI_LE_PERIODIC_SYNC_REPORTS_DISABLED_MASK,
                use_list=use_list,
            )
        )
        self.controller._send_hci_command_status(status, command.op_code)

    def on_hci_le_read_periodic_advertiser_list_size_command(self, command):
        '''
        See Bluetooth spec Vol 4, Part E - 7.8.73 LE Read Periodic Advertiser List Size
        Command
        '''
        return hci.HCI_LE_Read_Periodic_Advertiser_List_Size_ReturnParameters(
            SUCCESS, CONTROLLER_PERIODIC_ADVERTISER_LIST_SIZE
        )

    def _edit_periodic_list(self, command, add):
        """Periodic Advertiser List edits (Vol 4, Part E, 7.8.70, 7.8.71)."""
        if self.link.sync is not None:
            return hci.HCI_StatusReturnParameters(DISALLOWED)
        if (
            command.advertiser_address_type
            not in (hci.AddressType.PUBLIC_DEVICE, hci.AddressType.RANDOM_DEVICE)
            or not 0 <= command.advertising_sid <= PDU_ADV_ADI_SID_MAX
        ):
            return hci.HCI_StatusReturnParameters(INVALID)
        key = (
            hci.Address(
                bytes(command.advertiser_address), command.advertiser_address_type
            ),
            command.advertising_sid,
        )
        return hci.HCI_StatusReturnParameters(
            self.ll.edit_periodic_list(
                key, add, CONTROLLER_PERIODIC_ADVERTISER_LIST_SIZE
            )
        )

    def on_hci_le_add_device_to_periodic_advertiser_list_command(self, command):
        '''
        See Bluetooth spec Vol 4, Part E - 7.8.70 LE Add Device To Periodic Advertiser
        List Command
        '''
        return self._edit_periodic_list(command, True)

    def on_hci_le_remove_device_from_periodic_advertiser_list_command(self, command):
        '''
        See Bluetooth spec Vol 4, Part E - 7.8.71 LE Remove Device From Periodic
        Advertiser List Command
        '''
        return self._edit_periodic_list(command, False)

    def on_hci_le_clear_periodic_advertiser_list_command(self, command):
        return hci.HCI_StatusReturnParameters(
            self.ll.edit_periodic_list(
                None, False, CONTROLLER_PERIODIC_ADVERTISER_LIST_SIZE
            )
        )

    def on_hci_le_periodic_advertising_create_sync_cancel_command(self, command):
        '''
        See Bluetooth spec Vol 4, Part E - 7.8.68 LE Periodic Advertising Create Sync
        Cancel Command
        '''
        sync = self.ll.cancel_synchronizing()
        if sync is None:
            return hci.HCI_StatusReturnParameters(DISALLOWED)
        asyncio.get_running_loop().call_soon(
            self.on_sync_established,
            sync,
            hci.HCI_ErrorCode.OPERATION_CANCELLED_BY_HOST_ERROR,
        )
        return hci.HCI_StatusReturnParameters(SUCCESS)

    def on_hci_le_periodic_advertising_terminate_sync_command(self, command):
        return hci.HCI_StatusReturnParameters(
            self.ll.terminate_synchronization(command.sync_handle)
        )

    def on_hci_le_set_periodic_advertising_receive_enable_command(self, command):
        '''
        See Bluetooth spec Vol 4, Part E - 7.8.88 LE Set Periodic Advertising Receive
        Enable Command
        '''
        sync = self.link.syncs.get(command.sync_handle)
        if sync is None:
            return hci.HCI_StatusReturnParameters(
                hci.HCI_ErrorCode.UNKNOWN_CONNECTION_IDENTIFIER_ERROR
            )
        if command.enable not in (0, 1):
            return hci.HCI_StatusReturnParameters(UNSUPPORTED)
        self.ll.enable_periodic_reports(command.sync_handle, bool(command.enable))
        return hci.HCI_StatusReturnParameters(SUCCESS)
