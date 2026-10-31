# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Run unchanged Host scenarios against both Controller implementations."""

import pytest
from tests.integration.applications import require_artifact

from bsworld.devices import BSController, Controller, ZephyrController


def require_controller(controller_type: type[Controller]) -> None:
    """Skip when the selected Controller needs an artifact that was not built."""
    if controller_type is ZephyrController:
        require_artifact("BSWORLD_BT_VIRT_CONTROLLER_BIN", guide="docs/controllers.md")


@pytest.fixture(params=[ZephyrController, BSController], ids=["zephyr", "bscontroller"])
def controller_type(request):
    require_controller(request.param)
    return request.param


@pytest.fixture
def bsworld_default_controller_type(controller_type):
    # Overrides the framework fixture, so the `topo` fixture keeps its own
    # lifecycle and per-node output directories. Explicit controller_type
    # arguments can still select a mixed topology.
    return controller_type


__all__ = ["bsworld_default_controller_type", "controller_type", "require_controller"]
