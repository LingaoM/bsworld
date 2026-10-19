# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""BTSak currently runs against the Zephyr Controller only."""

import pytest

from bsworld.devices import ZephyrController


@pytest.fixture(params=[ZephyrController], ids=["zephyr"])
def controller_type(request):
    return request.param
