# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Changes committed when a connection event reaches a control-procedure Instant."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bscontroller.linklayer.parameters import Parameters


@dataclass(frozen=True)
class InstantUpdate:
    instant: int
    parameters: Parameters | None = None
    channel_map: int | None = None
    central_tx_phy: int = 0
    peripheral_tx_phy: int = 0
    local: bool = False
    anchor_reference: tuple[int, int] | None = None
    notify: bool | None = None
