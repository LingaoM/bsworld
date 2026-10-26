# Copyright 2018 Oticon A/S
# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Convert BabbleSim Tx CSV dumps to the Ellisys Bluetooth import format.

Port of ext_2G4_phy_v1/dump_post_process/convert_results_to_ellisysv2.sh.
Keep its header, fixed RSSI, Coded segment handling and numeric/lexical sort
order so existing traces remain identical, including duplicate records.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TextIO

_HEADER = (
    "FileFormat:Bluetooth\n                version=1.0\n\nItemFormat:LE version=1.1\n"
)


def convert_tx_csv(tx_files: Iterable[Path], output: TextIO) -> None:
    """Merge dumps in input order and write a time-sorted .bttrp trace."""
    records: list[tuple[int, str]] = []
    timestamp = "0"
    address = ""
    channel = 0
    rssi = 0
    ci = ""
    for path in tx_files:
        with path.open() as source:
            next(source, None)  # Each device dump has its own CSV header.
            for line in source:
                fields = line.removesuffix("\n").split(",")
                if len(fields) != 10 or not fields[9]:
                    continue
                packet = fields[9]
                modulation = int(fields[4])
                if modulation == 80 and int(fields[8]) > 4:
                    # FEC2 inherits the FEC1 timestamp, address, channel and CI.
                    phy = f"Coded coding=Coded{8 if ci == '00' else 2}"
                else:
                    # Match awk's double arithmetic and %.0f timestamp format.
                    timestamp = f"{float(fields[0]) * 1000:.0f}"
                    channel = int((float(fields[2]) - 2) / 2)
                    address = fields[3]
                    rssi = -40
                    if len(packet) >= 2:
                        ci = packet[:2]
                    if modulation == 16:
                        phy = "1Mbps"
                    elif modulation in (32, 33):
                        phy = "2Mbps"
                    else:
                        continue
                record = (
                    f'{timestamp} aa={address} rssi={rssi} rfchannel={channel} '
                    f'phy={phy} rawdata="{packet.rstrip()}"'
                )
                records.append((int(timestamp), record))

    output.write(_HEADER)
    # GNU sort -g breaks numeric ties by comparing the entire line.
    for _, record in sorted(records):
        output.write(f"Item time={record}\n")
