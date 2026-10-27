# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Independent privacy stimuli and observations at the HCI/RF boundaries."""

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from bscontroller import hci
from bscontroller.linklayer import LL_IFS_US, AdvertisingPduType
from bscontroller.radio.base import Phy
from tests.qualification.tester import (
    PEER_ADDRESS,
    adv_pdu,
    aux_pointer,
    ext_pdu,
    scan_parameters,
)

PEER_IRK = bytes.fromhex('00112233445566778899aabbccddeeff')
LOCAL_IRK = bytes.fromhex('ffeeddccbbaa99887766554433221100')
FALLBACK = hci.Address('01:23:45:67:89:AB')


def private_address(key, value=0x456789):
    """Core Vol 3, Part H, 2.2.2: test-side AES ah, HCI octet order."""
    prand = value.to_bytes(3, 'little')
    cipher = Cipher(algorithms.AES(key[::-1]), modes.ECB()).encryptor()
    result = cipher.update(bytes(13) + prand[::-1])[-3:][::-1]
    return hci.Address(result + prand)


def check_private_address(address, key):
    assert address.is_resolvable
    assert private_address(key, int.from_bytes(bytes(address)[3:], 'little')) == address


async def add_peer(
    tester,
    *,
    identity=PEER_ADDRESS,
    peer_irk=PEER_IRK,
    local_irk=LOCAL_IRK,
    device=False,
    enabled=True,
):
    await tester.command(
        hci.HCI_LE_Add_Device_To_Resolving_List_Command(
            identity.address_type,
            identity,
            peer_irk,
            local_irk,
        )
    )
    if device:
        await tester.command(
            hci.HCI_LE_Set_Privacy_Mode_Command(
                identity.address_type,
                identity,
                1,
            )
        )
    if enabled:
        await tester.command(hci.HCI_LE_Set_Address_Resolution_Enable_Command(1))


async def scanning(tester, *, active=False, extended=False, policy=0, own_type=0):
    parameters = (
        {'scan_types': [int(active)], 'scan_intervals': [16], 'scan_windows': [16]}
        if extended
        else {
            'le_scan_type': int(active),
            'le_scan_interval': 16,
            'le_scan_window': 16,
        }
    )
    await tester.command(
        scan_parameters(
            extended=extended,
            scanning_filter_policy=policy,
            own_address_type=own_type,
            **parameters,
        )
    )
    await scan_enable(tester, True, extended=extended)


async def scan_enable(tester, enable, *, extended=False):
    await tester.command(
        hci.HCI_LE_Set_Extended_Scan_Enable_Command(int(enable), 0, 0, 0)
        if extended
        else hci.HCI_LE_Set_Scan_Enable_Command(int(enable), 0)
    )


def reports(tester):
    found = []
    while (
        event := tester.take(
            lambda value: isinstance(
                value,
                (
                    hci.HCI_LE_Advertising_Report_Event,
                    hci.HCI_LE_Extended_Advertising_Report_Event,
                    hci.HCI_LE_Directed_Advertising_Report_Event,
                ),
            )
        )
    ) is not None:
        found.extend(event.reports)
    return found


async def advertising_event(
    tester,
    *,
    address=PEER_ADDRESS,
    channel=37,
    active=False,
    extended=False,
    decision=False,
    data=b'privacy',
    decision_data=b'\0',
    mode=0,
    primary_address=None,
    tx_power=None,
    power_dbm=0,
    kind=None,
    response_address=None,
    target=None,
    phy=Phy.LE_1M,
):
    """One Lower Tester event; return an optional SCAN_REQ observed over RF."""
    start = tester.radio.now_us + 200
    if extended or decision:
        await tester.transmit(
            channel,
            ext_pdu(
                kind=AdvertisingPduType.ADV_DECISION_IND
                if decision
                else AdvertisingPduType.ADV_EXT_IND,
                mode=mode,
                address=primary_address,
                adi=0x3000,
                aux=aux_pointer(0, 900, phy),
                data=decision_data if decision else b'',
                tx_power=tx_power,
            ),
            start_us=start,
            power_dbm=power_dbm,
        )
        end = await tester.transmit(
            0,
            ext_pdu(
                address=address,
                mode=mode,
                adi=0x3000,
                data=b'' if mode == 2 else data,
                target=target,
            ),
            start_us=start + 900,
            phy=phy,
            power_dbm=power_dbm,
        )
        request_channel = 0
    else:
        pdu = adv_pdu(
            kind
            if kind is not None
            else (
                AdvertisingPduType.ADV_SCAN_IND
                if active
                else AdvertisingPduType.ADV_NONCONN_IND
            ),
            address=address,
            data=data,
        )
        end = await tester.transmit(channel, pdu, start_us=start, power_dbm=power_dbm)
        request_channel = channel
    request = None
    if active:
        request = await tester.receive(request_channel, duration_us=500, phy=phy)
        if request is not None:
            assert request.pdu[0] & 15 == AdvertisingPduType.SCAN_REQ
            assert abs(request.start_us - end - LL_IFS_US) <= 2
            assert request.pdu[8:14] == bytes(address)
            source = address if response_address is None else response_address
            response = (
                ext_pdu(address=source, data=data, adi=0x3000)
                if extended or decision
                else adv_pdu(AdvertisingPduType.SCAN_RSP, address=source, data=data)
            )
            await tester.transmit(
                request_channel, response, start_us=request.end_us + LL_IFS_US, phy=phy
            )
    await tester.wait(1000)
    return request


async def observe_advertising(tester, *, duration_us=100_000, **parameters):
    """Advertise for a complete observation interval, covering all primary channels."""
    deadline = tester.radio.now_us + duration_us
    requests = []
    channel = 37
    while tester.radio.now_us < deadline:
        request = await advertising_event(tester, channel=channel, **parameters)
        if request is not None:
            requests.append(request)
        channel = 37 + (channel - 36) % 3
    return reports(tester), requests
