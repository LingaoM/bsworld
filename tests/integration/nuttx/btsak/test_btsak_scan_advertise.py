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
"""NuttX BTSak host tests over BSWorld Virtual Controllers."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest
from tests.integration.nuttx.btsak.devices import (
    NUTTX_BTSAK_ADVERTISER,
    NUTTX_BTSAK_SCANNER,
    nuttx_btsak_advertiser,
    nuttx_btsak_scanner,
)
from tests.integration.nuttx.common import NuttXProcessProfile, load_nuttx_profile, require_binaries

from bsworld.devices.instance import ProcessInstance
from bsworld.interference import StaticAttenuation

_DISCOVERY_TIMEOUT = 20.0
_BT_IFACE = "bnep0"
_BLE_ADVERTISING_CHANNELS_MHZ = (2402.0, 2426.0, 2480.0)
_INTERFERENCE_END_US = 5_000_000
_SCAN_ADDR_PATTERN = r"\d+\.\s+addr:\s+(?P<addr>(?:[0-9a-f]{2}:){5}[0-9a-f]{2})\s+type:"
_SCAN_ADDR_RE = re.compile(_SCAN_ADDR_PATTERN, re.IGNORECASE)
_ZERO_ADDR = "00:00:00:00:00:00"


@dataclass
class ScanAdvertiseNetwork:
    scanners: list[ProcessInstance]
    advertisers: list[ProcessInstance]


def _load_network(
    topo,
    *,
    scanners: Sequence[NuttXProcessProfile],
    advertisers: Sequence[NuttXProcessProfile],
) -> ScanAdvertiseNetwork:
    profiles = [*scanners, *advertisers]
    require_binaries(profiles)

    loaded_scanners = [
        load_nuttx_profile(
            topo,
            profile,
            log_subdir=Path("nuttx") / "scanners" / profile.name,
        )
        for profile in scanners
    ]
    loaded_advertisers = [
        load_nuttx_profile(
            topo,
            profile,
            log_subdir=Path("nuttx") / "advertisers" / profile.name,
        )
        for profile in advertisers
    ]
    return ScanAdvertiseNetwork(
        scanners=loaded_scanners,
        advertisers=loaded_advertisers,
    )


async def _start_roles(network: ScanAdvertiseNetwork) -> None:
    for advertiser in network.advertisers:
        await advertiser.shell.run_many((
            f"ifup {_BT_IFACE}", f"bt {_BT_IFACE} advertise start",
        ))
    for scanner in network.scanners:
        commands = [f"ifup {_BT_IFACE}", f"bt {_BT_IFACE} scan start"]
        for _ in range(20):
            commands.extend(("sleep 1", f"bt {_BT_IFACE} scan get"))
        await scanner.shell.run_many(commands)


async def _wait_scan_results(
    scanner: ProcessInstance,
    expected_count: int,
    *,
    timeout: float = _DISCOVERY_TIMEOUT,
) -> set[str]:
    addresses: set[str] = set()
    while len(addresses) < expected_count:
        line = await scanner.wait_log(_SCAN_ADDR_PATTERN, timeout=timeout)
        match = _SCAN_ADDR_RE.search(line)
        if match is None:
            continue
        addr = match.group("addr").lower()
        if addr != _ZERO_ADDR:
            addresses.add(addr)
    return addresses


async def test_nuttx_btsak_scanner_finds_advertiser(topo):
    network = _load_network(
        topo,
        scanners=[NUTTX_BTSAK_SCANNER],
        advertisers=[NUTTX_BTSAK_ADVERTISER],
    )
    await topo.start()
    await _start_roles(network)
    await _wait_scan_results(network.scanners[0], 1)


async def test_nuttx_btsak_shell_commands_can_stage_scan(topo):
    network = _load_network(
        topo,
        scanners=[NUTTX_BTSAK_SCANNER],
        advertisers=[NUTTX_BTSAK_ADVERTISER],
    )

    await topo.start()

    scanner = network.scanners[0]
    advertiser = network.advertisers[0]
    await advertiser.shell.run(f"ifup {_BT_IFACE}")
    await scanner.shell.run(f"ifup {_BT_IFACE}")
    await advertiser.shell.run(f"bt {_BT_IFACE} advertise start")
    await scanner.shell.run(f"bt {_BT_IFACE} scan start")
    for _ in range(20):
        await scanner.shell.run("sleep 1")
        await scanner.shell.run(f"bt {_BT_IFACE} scan get")

    await _wait_scan_results(scanner, 1)


async def test_nuttx_btsak_scanner_finds_multiple_advertisers(topo):
    network = _load_network(
        topo,
        scanners=[nuttx_btsak_scanner(0)],
        advertisers=[
            nuttx_btsak_advertiser(0),
            nuttx_btsak_advertiser(1),
        ],
    )
    await topo.start()
    await _start_roles(network)
    await _wait_scan_results(network.scanners[0], 2)


async def test_nuttx_btsak_targeted_interference_isolates_and_recovers(topo):
    network = _load_network(
        topo,
        scanners=[nuttx_btsak_scanner(0), nuttx_btsak_scanner(1)],
        advertisers=[nuttx_btsak_advertiser(0)],
    )
    protected_scanner, jammed_scanner = network.scanners
    advertiser = network.advertisers[0]
    jammers = [
        topo.add_burst_interference(
            frequency_mhz,
            power_dbm=20.0,
            interf_type="CW",
            windows=[(1, _INTERFERENCE_END_US)],
        )
        for frequency_mhz in _BLE_ADVERTISING_CHANNELS_MHZ
    ]
    topo.set_channel_attenuation(
        default_db=100.0,
        static_paths=[
            StaticAttenuation(tx=advertiser, rx=protected_scanner, attenuation_db=45.0),
            StaticAttenuation(tx=advertiser, rx=jammed_scanner, attenuation_db=45.0),
            *(
                StaticAttenuation(tx=jammer, rx=protected_scanner, attenuation_db=100.0)
                for jammer in jammers
            ),
            *(
                StaticAttenuation(tx=jammer, rx=jammed_scanner, attenuation_db=0.0)
                for jammer in jammers
            ),
        ],
    )

    await topo.start()
    await _start_roles(network)

    advertiser_address = advertiser.controller.public_address
    assert advertiser_address is not None
    advertiser_pattern = rf"\d+\.\s+addr:\s+{re.escape(advertiser_address.lower())}\s+type:"

    await protected_scanner.wait_log(advertiser_pattern, timeout=_DISCOVERY_TIMEOUT)
    with pytest.raises(TimeoutError):
        await jammed_scanner.wait_log(advertiser_pattern, timeout=2.0)
    await jammed_scanner.wait_log(advertiser_pattern, timeout=_DISCOVERY_TIMEOUT)
