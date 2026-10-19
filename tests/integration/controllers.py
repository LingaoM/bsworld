# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Run unchanged Host scenarios against both Controller implementations."""

from functools import partial

import pytest

from bsworld.devices import BSController, ZephyrController


@pytest.fixture(params=[ZephyrController, BSController], ids=["zephyr", "bscontroller"])
def controller_type(request):
    return request.param


@pytest.fixture
def topo(topo, controller_type, monkeypatch):
    # Keep the framework fixture's lifecycle and per-node output directories.
    # Explicit controller_type arguments can still select a mixed topology.
    monkeypatch.setattr(topo, "add_controller", partial(topo.add_controller, controller_type=controller_type))
    return topo
