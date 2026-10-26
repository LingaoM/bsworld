# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""One IUT connection per scenario; role is chosen by the scenario itself."""

import pytest

from tests.unit.linklayer.llcp.harness import CENTRAL, PERIPHERAL, LlcpHarness


@pytest.fixture
def iut(controller):
    """Factory: ``iut(role)`` returns a fresh established connection harness."""
    harnesses = []

    def create(role):
        harness = LlcpHarness(controller, role)
        harnesses.append(harness)
        return harness

    yield create
    for harness in harnesses:
        harness.close()


@pytest.fixture
def central(iut):
    return iut(CENTRAL)


@pytest.fixture
def peripheral(iut):
    return iut(PERIPHERAL)
