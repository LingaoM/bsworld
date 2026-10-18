# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""HCI buffer capacity and capability encodings (Core 6.3, Vol 4, Part E)."""

from bscontroller.linklayer.pdu import PDU_DATA_PAYLOAD_SIZE_MAX

HCI_ACL_BUFFER_SIZE = PDU_DATA_PAYLOAD_SIZE_MAX

HCI_SUPPORTED_STATE_MASK = (1 << 42) - 1

HCI_RSSI_NOT_AVAILABLE = 0x7F


# Vol 4, Part E, 7.3.93/94: HCI timeout fields use 10 ms units.
HCI_AUTHENTICATED_PAYLOAD_TIMEOUT_UNIT_US = 10_000
