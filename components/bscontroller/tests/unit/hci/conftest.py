# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""One Controller per HCI scenario, wired to a Host byte sink."""

import pytest

from tests.unit.hci.harness import HciHarness


@pytest.fixture
def host():
    """A Host that has unmasked every event."""
    harness = HciHarness()
    yield harness
    harness.close()


@pytest.fixture
def fresh():
    """A Host that has sent nothing: power-on defaults apply."""
    harness = HciHarness(unmask=False)
    yield harness
    harness.close()


@pytest.fixture
def configured():
    """Build Hosts whose Controller uses a given ``ControllerConfig``."""
    harnesses = []

    def build(config):
        harness = HciHarness(config=config)
        harnesses.append(harness)
        return harness

    yield build
    for harness in harnesses:
        harness.close()
