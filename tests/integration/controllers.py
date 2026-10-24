# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Run unchanged Host scenarios against both Controller implementations."""

import pytest

from bsworld.devices import BSController, ZephyrController


@pytest.fixture(params=[ZephyrController, BSController], ids=["zephyr", "bscontroller"])
def controller_type(request):
    return request.param


@pytest.fixture
def bsworld_default_controller_type(controller_type):
    # Overrides the framework fixture, so the `topo` fixture keeps its own
    # lifecycle and per-node output directories. Explicit controller_type
    # arguments can still select a mixed topology.
    return controller_type
