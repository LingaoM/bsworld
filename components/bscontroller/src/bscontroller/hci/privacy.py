# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Privacy commands (Core Vol 4, Part E, 7.8.38-45 and 7.8.77).

Decode identities and encode return values here; resolving records, command
exclusion and private-address clocks belong to the LL service.
"""

from bscontroller import hci
from bscontroller.hci.context import INVALID, LeControllerContext


class LePrivacyCommands(LeControllerContext):
    def _identity(self, command):
        """Decode the identity address/type used as the LL resolving-list key."""
        return hci.Address(
            bytes(command.peer_identity_address), command.peer_identity_address_type
        )

    def on_hci_le_add_device_to_resolving_list_command(self, command):
        """Add an identity and its IRKs (Core Vol 4, Part E, 7.8.38).

        LL owns capacity, duplicate-key checks and activity restrictions, and
        copies the identity and keys into a new resolving record on success.
        """
        return hci.HCI_StatusReturnParameters(
            self.ll.privacy.add(
                self._identity(command), command.peer_irk, command.local_irk
            )
        )

    def on_hci_le_remove_device_from_resolving_list_command(self, command):
        """Remove one resolving record (Core Vol 4, Part E, 7.8.39).

        Reject non-identity address types here; LL checks activity restrictions
        and record existence before removing the identity and its cached RPAs.
        """
        if command.peer_identity_address_type not in (
            hci.AddressType.PUBLIC_DEVICE,
            hci.AddressType.RANDOM_DEVICE,
        ):
            return hci.HCI_StatusReturnParameters(INVALID)
        return hci.HCI_StatusReturnParameters(
            self.ll.privacy.remove(self._identity(command))
        )

    def on_hci_le_clear_resolving_list_command(self, _command):
        """Clear resolving records (Core Vol 4, Part E, 7.8.40).

        Use LL's bulk-removal path so clearing obeys the same activity guard
        as removal of a single record.
        """
        return hci.HCI_StatusReturnParameters(self.ll.privacy.remove(None))

    def on_hci_le_read_resolving_list_size_command(self, _command):
        """Report configured total capacity (Core Vol 4, Part E, 7.8.41).

        This is the supported number of records, independent of current usage.
        """
        return hci.HCI_LE_Read_Resolving_List_Size_ReturnParameters(
            hci.HCI_ErrorCode.SUCCESS, self.controller.config.resolving_list_size
        )

    def _read_rpa(self, command, *, local):
        """Read a cached RPA by identity; reading does not generate an address.

        Shared by the peer/local commands in Core Vol 4, Part E, 7.8.42-43.
        LL returns an address copy or the all-zero random-address placeholder
        when the record exists but its selected RPA has not been populated.
        """
        if command.peer_identity_address_type not in (
            hci.AddressType.PUBLIC_DEVICE,
            hci.AddressType.RANDOM_DEVICE,
        ):
            return INVALID, hci.Address.ANY_RANDOM
        return self.ll.privacy.read_rpa(self._identity(command), local=local)

    def on_hci_le_read_peer_resolvable_address_command(self, command):
        """Encode the cached peer RPA (Core Vol 4, Part E, 7.8.42)."""
        return hci.HCI_LE_Read_Peer_Resolvable_Address_ReturnParameters(
            *self._read_rpa(command, local=False)
        )

    def on_hci_le_read_local_resolvable_address_command(self, command):
        """Encode the cached local RPA (Core Vol 4, Part E, 7.8.43)."""
        return hci.HCI_LE_Read_Local_Resolvable_Address_ReturnParameters(
            *self._read_rpa(command, local=True)
        )

    def on_hci_le_set_address_resolution_enable_command(self, command):
        """Toggle LL address resolution (Core Vol 4, Part E, 7.8.44).

        LL checks discovery activity even when resolution is currently disabled;
        changing the enable flag retains resolving records and privacy modes.
        """
        return hci.HCI_StatusReturnParameters(
            self.ll.privacy.set_enabled(command.address_resolution_enable)
        )

    def on_hci_le_set_resolvable_private_address_timeout_command(self, command):
        """Set a fixed RPA lifetime, in seconds (Core Vol 4, Part E, 7.8.45 v1).

        Map v1 onto LL's shared timeout-range implementation with equal bounds.
        """
        return hci.HCI_StatusReturnParameters(
            self.ll.privacy.set_timeout(command.rpa_timeout, command.rpa_timeout)
        )

    def on_hci_le_set_resolvable_private_address_timeout_v2_command(self, command):
        """Set the RPA lifetime range (Core Vol 4, Part E, 7.8.45 v2).

        Pass bounds in seconds to LL, which validates their range and ordering.
        LL draws a lifetime from this range when refreshing a private address.
        """
        return hci.HCI_StatusReturnParameters(
            self.ll.privacy.set_timeout(
                command.rpa_timeout_min, command.rpa_timeout_max
            )
        )

    def on_hci_le_set_privacy_mode_command(self, command):
        """Set an identity's privacy mode (Core Vol 4, Part E, 7.8.77).

        LL validates the identity, mode and activity restrictions before changing
        the record; address-resolution enable remains a separate setting.
        """
        return hci.HCI_StatusReturnParameters(
            self.ll.privacy.set_mode(self._identity(command), command.privacy_mode)
        )
