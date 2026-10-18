# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Controller resource capacities and supported PHYs; implementation limits."""

CONTROLLER_SUPPORTED_PHY_MASK = 0b111

CONTROLLER_ADVERTISING_SET_COUNT = 8

CONTROLLER_PERIODIC_SYNC_COUNT = 8

CONTROLLER_CONNECTION_COUNT = 8

CONTROLLER_PERIODIC_ADVERTISER_LIST_SIZE = 8

CONTROLLER_PRIMARY_SCAN_PHY_MASK = 0b101


# Maximum combined extended advertising data retained by this Controller.
CONTROLLER_ADV_DATA_SIZE_MAX = 1650
