# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""One IUT Controller per scenario, on a scripted radio."""

import pytest

from tests.unit.linklayer.air.harness import AirHarness


@pytest.fixture
def iut():
    harness = AirHarness()
    yield harness
    harness.close()
