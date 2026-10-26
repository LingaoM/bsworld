# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

from io import StringIO

import pytest

from bsworld.backends.ellisys import convert_tx_csv

HEADER = (
    "FileFormat:Bluetooth\n                version=1.0\n\nItemFormat:LE version=1.1\n"
)
CSV_HEADER = (
    "start_time,end_time,center_freq,phy_address,modulation,power_level,"
    "abort_time,recheck_time,packet_size,packet\n"
)


def test_merge_sorts_by_time_then_full_record_and_keeps_duplicates(tmp_path) -> None:
    first = tmp_path / "first.Tx.csv"
    first.write_text(
        CSV_HEADER
        + "20,39,4,0xBBBBBBBB,32,0,0,0,5,01 00 00 00 00   \n"
        + "10,29,2,0x8E89BED6,16,0,0,0,5,02 00 00 00 00\n"
    )
    second = tmp_path / "second.Tx.csv"
    second.write_text(
        CSV_HEADER
        + "20,39,80,0xAAAAAAAA,33,0,0,0,5,03 00 00 00 00\n"
        + "10,29,2,0x8E89BED6,16,0,0,0,5,02 00 00 00 00\n"
    )
    output = StringIO()

    convert_tx_csv([first, second], output)

    assert output.getvalue() == (
        HEADER
        + (
            'Item time=10000 aa=0x8E89BED6 rssi=-40 rfchannel=0 phy=1Mbps rawdata="02 '
            '00 00 00 00"\n'
        )
        + (
            'Item time=10000 aa=0x8E89BED6 rssi=-40 rfchannel=0 phy=1Mbps rawdata="02 '
            '00 00 00 00"\n'
        )
        + (
            'Item time=20000 aa=0xAAAAAAAA rssi=-40 rfchannel=39 phy=2Mbps rawdata="03 '
            '00 00 00 00"\n'
        )
        + (
            'Item time=20000 aa=0xBBBBBBBB rssi=-40 rfchannel=1 phy=2Mbps rawdata="01 '
            '00 00 00 00"\n'
        )
    )


@pytest.mark.parametrize(("ci", "coding"), [("00", 8), ("01", 2)])
def test_coded_fec2_uses_fec1_timestamp_and_coding(tmp_path, ci, coding) -> None:
    path = tmp_path / "coded.Tx.csv"
    path.write_text(
        CSV_HEADER
        + f"100,475,2,0x8E89BED6,80,0,0,0,1,{ci}\n"
        + "476,600,2,0x8E89BED6,80,0,0,0,5,01 00 AA BB CC\n"
    )
    output = StringIO()

    convert_tx_csv([path], output)

    assert output.getvalue() == (
        HEADER + 'Item time=100000 aa=0x8E89BED6 rssi=-40 rfchannel=0 '
        f'phy=Coded coding=Coded{coding} '
        'rawdata="01 00 AA BB CC"\n'
    )


def test_ignores_non_ble_empty_and_truncated_records(tmp_path) -> None:
    path = tmp_path / "partial.Tx.csv"
    path.write_text(
        CSV_HEADER
        + "1,20,2,0x8E89BED6,256,0,0,0,5,01 00 00 00 00\n"
        + "2,20,2,0x8E89BED6,16,0,0,0,0,\n"
        + "3,20,2,0x8E89BED6,16,0,0,0\n\n"
    )
    output = StringIO()

    convert_tx_csv([path], output)

    assert output.getvalue() == HEADER


def test_empty_dump_writes_the_import_header(tmp_path) -> None:
    path = tmp_path / "empty.Tx.csv"
    path.touch()
    output = StringIO()

    convert_tx_csv([path], output)

    assert output.getvalue() == HEADER
