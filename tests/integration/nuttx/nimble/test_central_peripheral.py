# Copyright 2026 Xiaomi Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""NuttX NimBLE host tests over BSWorld Virtual Controllers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from tests.integration.nuttx.common import create_nuttx_process, require_binaries
from tests.integration.nuttx.nimble.devices import (
    DEFAULT_DEVICE_NAME,
    NUTTX_NIMBLE_CENTRAL,
    NUTTX_NIMBLE_PERIPHERAL,
)

from bsworld.devices.instance import ProcessInstance

_DISCOVERY_TIMEOUT = 30.0
_CONNECT_TIMEOUT = 30.0
_GATT_TIMEOUT = 30.0


@dataclass
class NimbleNetwork:
    central: ProcessInstance
    peripheral: ProcessInstance


def _build_network(topo) -> NimbleNetwork:
    profiles = [NUTTX_NIMBLE_CENTRAL, NUTTX_NIMBLE_PERIPHERAL]
    require_binaries(profiles)
    central = create_nuttx_process(
        topo, NUTTX_NIMBLE_CENTRAL, log_subdir=Path("nuttx") / "nimble" / "central"
    )
    peripheral = create_nuttx_process(
        topo,
        NUTTX_NIMBLE_PERIPHERAL,
        log_subdir=Path("nuttx") / "nimble" / "peripheral",
    )
    for host, address in (
        (central, "C0:FF:EE:20:01:01"),
        (peripheral, "C0:FF:EE:20:00:01"),
    ):
        host.attach(topo.add_controller(public_address=address))
    return NimbleNetwork(central=central, peripheral=peripheral)


async def test_nuttx_nimble_central_connects_peripheral(topo):
    network = _build_network(topo)
    await topo.start()
    await network.central.shell.run_many(("ifup bnep0", "blecent"))
    await network.peripheral.shell.run_many(("ifup bnep0", "bleprph"))
    await network.central.wait_log(
        rf"name\(complete\)={re.escape(DEFAULT_DEVICE_NAME)}",
        timeout=_DISCOVERY_TIMEOUT,
    )
    await network.central.wait_log(
        r"Connection established handle=\d+",
        timeout=_CONNECT_TIMEOUT,
    )
    await network.peripheral.wait_log(
        r"connection established; status=0 handle=\d+",
        timeout=_CONNECT_TIMEOUT,
    )
    await network.central.wait_log(
        r"Service discovery complete; status=0 conn_handle=\d+",
        timeout=_GATT_TIMEOUT,
    )
    await network.central.wait_log(
        r"Subscribe complete; status=0 conn_handle=\d+ attr_handle=\d+",
        timeout=_GATT_TIMEOUT,
    )
