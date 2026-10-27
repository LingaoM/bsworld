# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Implementation capabilities fixed by this Controller (PHYs, codec limits).

Values the specification lets an implementation choose, such as buffer and list
sizes, are configurable through :class:`bscontroller.config.ControllerConfig`.
"""

CONTROLLER_SUPPORTED_PHY_MASK = 0b111

CONTROLLER_PRIMARY_SCAN_PHY_MASK = 0b101


# Maximum combined extended advertising data retained by this Controller.
CONTROLLER_ADV_DATA_SIZE_MAX = 1650
