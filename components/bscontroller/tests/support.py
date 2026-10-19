# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Host payload builders for Controller tests; independent wire values."""

L2CAP_LE_U_DYNAMIC_CID_RANGE_START = 0x0040
AD_COMPLETE_LOCAL_NAME = 0x09
AD_CHANNEL_MAP_UPDATE_INDICATION = 0x28
AD_PERIODIC_RESPONSE_TIMING_INFORMATION = 0x32


def advertising_data(structures):
    return b''.join(bytes([len(data) + 1, kind]) + data for kind, data in structures)


# Expected HCI wire values for this IUT, independent of implementation constants.
CONTROLLER_COMPANY_IDENTIFIER = 0xFFFF
AUTHENTICATED_PAYLOAD_TIMEOUT_DEFAULT = 3000
AUTHENTICATED_PAYLOAD_TIMEOUT_UNIT_US = 10_000
