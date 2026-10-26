# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Nonce limits, encrypted retries and safe key-refresh queue transitions."""

import pytest
from cryptography.exceptions import InvalidTag

from bscontroller import crypto, hci
from bscontroller.linklayer import (
    LL_CONN_INTERVAL_UNIT_US,
    LL_RESPONSE_TIMEOUT_US,
    PDU_DATA_MD_MASK,
    PDU_DATA_NESN_MASK,
    PDU_DATA_SN_MASK,
    PDU_HEADER_SIZE,
    ControlOpcode,
    LlId,
)
from bscontroller.linklayer.encryption import ENC_REQUEST, PacketCipher, State
from tests.unit.helpers import add_connection

ErrorCode = hci.HCI_ErrorCode

Opcode = ControlOpcode

KEY = bytes.fromhex('99AD1B5226A37E3E058E3B8E27C2C666')

IV = bytes.fromhex('24ABDCBABEBAAFDE')


def test_encryption_setup_remains_per_connection(connection):
    connection.role = hci.Role.CENTRAL
    second = add_connection(connection, 1)
    listener = connection.link.listener
    for value, key in ((connection, b'1' * 16), (second, b'2' * 16)):
        listener.on_hci_le_enable_encryption_command(
            hci.HCI_LE_Enable_Encryption_Command(
                value.handle,
                bytes(8),
                0,
                key,
            )
        )
        assert listener.controller.events[-1].status == ErrorCode.SUCCESS
        assert value.encryption.ltk == key
    assert connection.encryption is not second.encryption
    assert len(connection.queue) == len(second.queue) == 1


@pytest.mark.parametrize(
    'state,opcode',
    [
        (State.ENC_RSP, Opcode.LL_ENC_REQ),
        (State.KEY, Opcode.LL_ENC_RSP),
        (State.START_RSP, Opcode.LL_START_ENC_REQ),
        (State.START_RSP, Opcode.LL_START_ENC_RSP),
        (State.PAUSE_RSP, Opcode.LL_PAUSE_ENC_REQ),
        (State.PAUSE_ACK, Opcode.LL_PAUSE_ENC_RSP),
    ],
)
def test_encryption_control_queue_resets_timer_but_retransmission_does_not(connection, state, opcode):
    encryption = connection.encryption
    encryption.state = state
    encryption.deadline_us = 10
    connection.radio.now_us = 100
    encryption.enqueue(opcode)
    assert encryption.deadline_us == 100 + LL_RESPONSE_TIMEOUT_US
    connection.radio.now_us = 200
    encryption.sent(bytes([opcode]))
    encryption.sent(bytes([opcode]))
    assert encryption.deadline_us == 100 + LL_RESPONSE_TIMEOUT_US


def test_idle_ping_queue_does_not_start_encryption_procedure_timer(connection):
    connection.encryption.enqueue(Opcode.LL_PING_REQ)
    assert connection.encryption.deadline_us == 0


@pytest.mark.parametrize('central,expected', [(True, '9FCDA7F448'), (False, 'A34C13A415')])
def test_core_start_encryption_vector(central, expected):
    cipher = PacketCipher(KEY, IV, central=central)
    assert cipher.encrypt(LlId.CONTROL, bytes([Opcode.LL_START_ENC_RSP])) == bytes.fromhex(expected)


def test_ccm_masks_acknowledgement_bits_and_reuses_receive_counter():
    tx = PacketCipher(KEY, IV, central=True)
    rx = PacketCipher(KEY, IV, central=False)
    payload = tx.encrypt(LlId.START, b'encrypted payload')
    assert rx.decrypt(LlId.START, payload, duplicate=False) == b'encrypted payload'
    assert rx.decrypt(LlId.START | 0x1C, payload, duplicate=True) == b'encrypted payload'
    assert rx.rx_counter == tx.tx_counter == 1
    with pytest.raises(InvalidTag):
        rx.decrypt(LlId.CONTINUATION, payload, duplicate=True)


def test_empty_packets_have_no_mic_or_counter():
    cipher = PacketCipher(KEY, IV, central=True)
    assert cipher.encrypt(LlId.CONTINUATION, b'') == b''
    assert cipher.decrypt(LlId.CONTINUATION, b'', duplicate=False) == b''
    assert cipher.tx_counter == cipher.rx_counter == 0


def test_counter_exhaustion_never_reuses_a_nonce():
    cipher = PacketCipher(KEY, IV, central=True)
    receiver = PacketCipher(KEY, IV, central=False)
    cipher.tx_counter = (1 << 39) - 1
    receiver.rx_counter = (1 << 39) - 1
    wire = cipher.encrypt(LlId.START, b'last')
    assert receiver.decrypt(LlId.START, wire, duplicate=False) == b'last'
    assert receiver.decrypt(LlId.START, wire, duplicate=True) == b'last'
    with pytest.raises(OverflowError):
        cipher.encrypt(LlId.START, b'overflow')
    with pytest.raises(OverflowError):
        receiver.decrypt(LlId.START, wire, duplicate=False)


@pytest.mark.asyncio
async def test_encrypted_retransmission_preserves_ciphertext_and_counter(connection):
    connection.encryption.cipher = PacketCipher(KEY, IV, central=True)
    connection.encryption.tx_enabled = True
    connection.enqueue_acl(False, b'payload')
    await connection.send(0, 100)
    wire = connection.radio.sent[-1][2]
    await connection.send(0, connection.radio.now_us + 100)
    assert connection.radio.sent[-1][2] == wire
    assert connection.encryption.cipher.tx_counter == 1


def test_mic_failure_never_acknowledges_or_delivers_data(connection):
    connection.reported = True
    connection.encryption.cipher = PacketCipher(KEY, IV, central=False)
    connection.encryption.rx_enabled = True
    tx = PacketCipher(KEY, IV, central=True)
    payload = bytearray(tx.encrypt(LlId.START, b'bad mic'))
    payload[-1] ^= 1
    connection.accept(bytes([LlId.START, len(payload)]) + payload, True)
    assert connection.closed and connection.rx_nesn == 0
    assert (
        connection.link.listener.controller.events[-1].reason
        == hci.HCI_ErrorCode.CONNECTION_TERMINATED_DUE_TO_MIC_FAILURE_ERROR
    )


def test_unexpected_control_during_start_closes_connection(connection):
    connection.encryption.state = State.START_REQ
    connection.accept(bytes([LlId.CONTROL, 1, Opcode.LL_VERSION_IND]), True)
    assert connection.closed and connection.rx_nesn == 0


@pytest.mark.parametrize(
    'llid,payload',
    [(LlId.START, b'data'), (LlId.CONTROL, bytes([Opcode.LL_VERSION_IND]))],
)
def test_no_new_plaintext_procedure_while_host_key_is_pending(connection, llid, payload):
    connection.encryption.state = State.KEY
    connection.accept(bytes([llid, len(payload)]) + payload, True)
    assert connection.closed and connection.rx_nesn == 0


@pytest.mark.parametrize('opcode', [Opcode.LL_VERSION_IND, Opcode.LL_FEATURE_RSP, Opcode.LL_PING_RSP])
def test_overlapping_control_is_deferred_until_encryption_completes(connection, opcode):
    from bscontroller.linklayer.connection import Outbound

    connection.encryption.state = State.ENC_RSP
    connection.queue.append(Outbound(LlId.CONTROL, bytes([opcode])))
    assert connection._next_outbound().payload == b''
    connection.encryption.state = State.IDLE
    assert connection._next_outbound().payload == bytes([opcode])


def test_ping_budget_covers_request_alignment_and_peer_reply(connection):
    encryption = connection.encryption
    encryption.enabled = True
    encryption.last_authenticated_us = 100
    spacing = connection.parameters.interval * LL_CONN_INTERVAL_UNIT_US * (connection.parameters.latency + 1)
    assert encryption.next_deadline_us == 100 + encryption.auth_timeout_us - 2 * spacing


@pytest.mark.parametrize('key,iv', [(bytes(24), IV), (KEY, bytes(7))])
def test_cipher_rejects_non_le_key_or_iv(key, iv):
    with pytest.raises(ValueError, match='128-bit key'):
        PacketCipher(key, iv, central=True)


def test_failed_refresh_never_resumes_unencrypted_user_traffic(connection):
    connection.reported = True
    connection.role = hci.Role.CENTRAL
    encryption = connection.encryption
    encryption.enabled = encryption.tx_enabled = encryption.rx_enabled = True
    encryption.start(bytes(8), 0, KEY)
    encryption.finish(hci.HCI_ErrorCode.PIN_OR_KEY_MISSING_ERROR)
    assert connection.closed and not encryption.tx_enabled and not encryption.rx_enabled


def test_duplicate_pause_packet_survives_rx_mode_transition(connection):
    encryption = connection.encryption
    encryption.cipher = PacketCipher(KEY, IV, central=False)
    encryption.rx_enabled = True
    tx = PacketCipher(KEY, IV, central=True)
    wire = tx.encrypt(LlId.CONTROL, bytes([Opcode.LL_PAUSE_ENC_REQ]))
    assert encryption.receive(LlId.CONTROL, wire, duplicate=False) == bytes([Opcode.LL_PAUSE_ENC_REQ])
    encryption.rx_enabled = False
    encryption.state = State.PAUSE_ACK
    assert encryption.receive(LlId.CONTROL, wire, duplicate=True) == bytes([Opcode.LL_PAUSE_ENC_REQ])
    assert encryption.cipher.rx_counter == 1


def test_pre_encryption_plaintext_cannot_acknowledge_encrypted_data(connection):
    encryption = connection.encryption
    plain = bytes([Opcode.LL_VERSION_IND])
    assert encryption.receive(LlId.CONTROL, plain, duplicate=False) == plain
    encryption.cipher = PacketCipher(KEY, IV, central=False)
    encryption.rx_enabled = True
    assert encryption.receive(LlId.CONTROL, plain, duplicate=True) is None
    assert connection.closed


@pytest.mark.asyncio
async def test_paused_user_queue_sends_only_empty_packets_without_md(connection):
    connection.encryption.state = State.KEY
    connection.enqueue_acl(False, b'must wait for encryption')
    await connection.send(0, 100)
    packet = connection.radio.sent[-1][2]
    assert packet[PDU_HEADER_SIZE:] == b'' and not packet[0] & PDU_DATA_MD_MASK
    assert connection.queue[0].payload == b'must wait for encryption'


async def _request_key(connection, *, refresh=False, extended=False):
    connection.established = True
    connection.report_created()
    connection.peer_features = int(hci.LeFeatureMask.EXTENDED_REJECT_INDICATION) if extended else 0
    encryption = connection.encryption
    encryption.enabled = refresh
    encryption.state = State.RESTART if refresh else State.IDLE
    connection.control(bytes([Opcode.LL_ENC_REQ]) + ENC_REQUEST.pack(bytes(8), 0, bytes(8), bytes(4)))
    await connection.send(0, 100)
    connection.accept(bytes([LlId.CONTINUATION | PDU_DATA_NESN_MASK, 0]), True)
    assert encryption.state == State.KEY and encryption.deadline_us
    return encryption


@pytest.mark.asyncio
@pytest.mark.parametrize('acknowledge', [False, True], ids=['timeout', 'ack'])
async def test_missing_refresh_key_performs_acl_termination(connection, acknowledge):
    # Core Vol 6, Part B, 5.1.3.1: no LTK after a pause -> ACL Termination, PIN or Key Missing.
    encryption = await _request_key(connection, refresh=True)
    old_deadline = encryption.deadline_us
    connection.radio.now_us = connection.last_rx_us = old_deadline - 500_000
    connection.enqueue_acl(False, b'must not escape the failed refresh')
    encryption.supply_key(None)
    assert encryption.busy and not connection.closed
    termination = bytes([Opcode.LL_TERMINATE_IND, ErrorCode.PIN_OR_KEY_MISSING_ERROR])
    await connection.send(0, connection.radio.now_us + 100)
    assert connection.radio.sent[-1][2][PDU_HEADER_SIZE:] == termination
    assert not connection.radio.sent[-1][2][0] & PDU_DATA_MD_MASK
    connection.radio.now_us = old_deadline
    assert not connection.check_timeout()
    await connection.send(0, connection.radio.now_us + 100)
    assert connection.radio.sent[-1][2][PDU_HEADER_SIZE:] == termination
    # 5.1.6: the link closes on acknowledgment or T_terminate, not on transmission.
    assert not connection.closed and connection.termination_deadline_us
    if acknowledge:
        connection.accept(bytes([LlId.CONTINUATION | PDU_DATA_SN_MASK, 0]), True)
    else:
        connection.radio.now_us = connection.termination_deadline_us
        connection.check_timeout()
    assert connection.closed
    event = connection.link.listener.controller.events[-1]
    assert isinstance(event, hci.HCI_Disconnection_Complete_Event)
    assert event.reason == ErrorCode.PIN_OR_KEY_MISSING_ERROR


@pytest.mark.asyncio
@pytest.mark.parametrize('extended', [False, True], ids=['reject', 'extended-reject'])
@pytest.mark.parametrize('peer_data', [b'', b'peer data'], ids=['empty-ack', 'data-ack'])
async def test_missing_initial_key_keeps_acl_paused_until_rejection_ack(connection, extended, peer_data):
    # Core Vol 6, Part B, 5.1.3.1: the Peripheral completes rejection on its ACK.
    encryption = await _request_key(connection, extended=extended)
    user_data = b'queued ACL'
    connection.enqueue_acl(False, user_data)
    encryption.supply_key(None)
    rejection = bytes(
        [Opcode.LL_REJECT_EXT_IND, Opcode.LL_ENC_REQ, ErrorCode.PIN_OR_KEY_MISSING_ERROR]
        if extended
        else [Opcode.LL_REJECT_IND, ErrorCode.PIN_OR_KEY_MISSING_ERROR]
    )
    await connection.send(0, connection.radio.now_us + 100)
    assert connection.radio.sent[-1][2][PDU_HEADER_SIZE:] == rejection
    assert encryption.busy and not connection.radio.sent[-1][2][0] & PDU_DATA_MD_MASK

    # A bad-CRC ACK or valid packet retaining NESN must not release queued ACL.
    connection.accept(bytes([LlId.CONTINUATION | PDU_DATA_SN_MASK, 0]), False)
    oversized = bytes(connection.controls.data_length.local.rx_octets + 1)
    connection.accept(bytes([LlId.START | PDU_DATA_SN_MASK, len(oversized)]) + oversized, True)
    connection.accept(bytes([LlId.CONTINUATION | PDU_DATA_SN_MASK | PDU_DATA_NESN_MASK, 0]), True)
    assert encryption.busy
    await connection.send(0, connection.radio.now_us + 100)
    assert connection.radio.sent[-1][2][PDU_HEADER_SIZE:] == rejection

    # The peer may acknowledge the rejection and carry its first data in one PDU.
    header = LlId.START if peer_data else LlId.CONTINUATION
    connection.accept(bytes([header, len(peer_data)]) + peer_data, True)
    assert not connection.closed and not encryption.busy
    assert encryption.deadline_us == 0
    assert not encryption.enabled and not encryption.tx_enabled and not encryption.rx_enabled
    events = connection.link.listener.controller.events
    assert [event.data for event in events if isinstance(event, hci.HCI_AclDataPacket)] == (
        [peer_data] if peer_data else []
    )
    await connection.send(0, connection.radio.now_us + 100)
    assert connection.radio.sent[-1][2][PDU_HEADER_SIZE:] == user_data


@pytest.mark.asyncio
@pytest.mark.parametrize('transmit_rejection', [False, True], ids=['not-sent', 'not-acked'])
async def test_missing_initial_key_rejects_data_without_rejection_ack(connection, transmit_rejection):
    encryption = await _request_key(connection)
    encryption.supply_key(None)
    if transmit_rejection:
        await connection.send(0, connection.radio.now_us + 100)
    # Neither a guessed ACK before transmission nor data retaining NESN completes rejection.
    header = LlId.START | PDU_DATA_SN_MASK | (PDU_DATA_NESN_MASK if transmit_rejection else 0)
    connection.accept(bytes([header, 4]) + b'data', True)
    assert connection.closed
    assert (
        connection.link.listener.controller.events[-1].reason
        == ErrorCode.CONNECTION_TERMINATED_DUE_TO_MIC_FAILURE_ERROR
    )


@pytest.mark.asyncio
async def test_missing_initial_key_rejection_retains_response_timeout(connection):
    encryption = await _request_key(connection)
    connection.radio.now_us += 1000
    encryption.supply_key(None)
    deadline = connection.radio.now_us + LL_RESPONSE_TIMEOUT_US
    await connection.send(0, connection.radio.now_us + 100)
    connection.radio.now_us = connection.last_rx_us = deadline - 1
    assert not connection.check_timeout()
    connection.radio.now_us = deadline
    assert connection.check_timeout()
    assert connection.link.listener.controller.events[-1].reason == ErrorCode.LMP_OR_LL_RESPONSE_TIMEOUT_ERROR


async def _start_encryption_after_phy_request(connection, *, extended=False):
    connection.established = True
    connection.report_created()
    connection.peer_features = int(hci.LeFeatureMask.EXTENDED_REJECT_INDICATION) if extended else 0
    connection.controls.request_phy(1, 1)
    await connection.send(0, 100)
    assert connection.radio.sent[-1][2][PDU_HEADER_SIZE:] == bytes([Opcode.LL_PHY_REQ, 1, 1])
    request = bytes([Opcode.LL_ENC_REQ]) + ENC_REQUEST.pack(bytes(8), 0, bytes(8), bytes(4))
    connection.accept(bytes([LlId.CONTROL | PDU_DATA_NESN_MASK, len(request)]) + request, True)
    assert connection.encryption.state == State.KEY
    return connection.encryption


@pytest.mark.asyncio
@pytest.mark.parametrize('extended', [False, True], ids=['reject', 'extended-reject'])
@pytest.mark.parametrize('key_reply', ['before-enc-rsp', 'after-enc-rsp', 'after-unknown-rsp'])
async def test_delayed_phy_unknown_rsp_survives_key_rejection(connection, extended, key_reply):
    # Vol 6, Part B, 5.1.3.1 permits UNKNOWN_RSP for an earlier Peripheral PDU after ENC_RSP.
    encryption = await _start_encryption_after_phy_request(connection, extended=extended)
    user_data = b'queued during encryption'
    connection.enqueue_acl(False, user_data)
    if key_reply == 'before-enc-rsp':
        encryption.supply_key(None)
    await connection.send(0, connection.radio.now_us + 100)
    assert connection.radio.sent[-1][2][PDU_HEADER_SIZE] == Opcode.LL_ENC_RSP
    if key_reply == 'after-enc-rsp':
        encryption.supply_key(None)
    deadline = encryption.deadline_us

    # ACK ENC_RSP while answering the PHY request sent before encryption began.
    response = bytes([Opcode.LL_UNKNOWN_RSP, Opcode.LL_PHY_REQ])
    connection.accept(bytes([LlId.CONTROL | PDU_DATA_SN_MASK, len(response)]) + response, True)
    assert not connection.closed and encryption.busy
    assert encryption.deadline_us == deadline
    assert not connection.controls.phy_request and connection.controls.deadline_us == 0
    events = connection.link.listener.controller.events
    phy_events = [event for event in events if isinstance(event, hci.HCI_LE_PHY_Update_Complete_Event)]
    assert len(phy_events) == 1 and phy_events[0].status == ErrorCode.UNSUPPORTED_REMOTE_FEATURE_ERROR
    assert connection.queue[0].payload == user_data
    if key_reply == 'after-unknown-rsp':
        encryption.supply_key(None)

    await connection.send(0, connection.radio.now_us + 100)
    rejection = bytes(
        [Opcode.LL_REJECT_EXT_IND, Opcode.LL_ENC_REQ, ErrorCode.PIN_OR_KEY_MISSING_ERROR]
        if extended
        else [Opcode.LL_REJECT_IND, ErrorCode.PIN_OR_KEY_MISSING_ERROR]
    )
    assert connection.radio.sent[-1][2][PDU_HEADER_SIZE:] == rejection
    assert encryption.busy
    connection.accept(bytes([LlId.CONTINUATION | PDU_DATA_NESN_MASK, 0]), True)
    assert not connection.closed and not encryption.busy
    await connection.send(0, connection.radio.now_us + 100)
    assert connection.radio.sent[-1][2][PDU_HEADER_SIZE:] == user_data
    # Keep supervision alive beyond the old procedure deadline: no stale PHY timer may fire.
    connection.radio.now_us = connection.last_rx_us = deadline + 1
    assert not connection.check_timeout()


@pytest.mark.asyncio
@pytest.mark.parametrize('invalid', ['not-sent', 'wrong-opcode', 'wrong-length', 'wrong-llid'])
async def test_unknown_rsp_exception_requires_a_sent_peripheral_control(connection, invalid):
    encryption = await _start_encryption_after_phy_request(connection)
    encryption.supply_key(None)
    if invalid != 'not-sent':
        await connection.send(0, connection.radio.now_us + 100)
    response = bytes([Opcode.LL_UNKNOWN_RSP, Opcode.LL_PHY_REQ])
    if invalid == 'wrong-opcode':
        connection.enqueue_control(bytes([Opcode.LL_VERSION_IND]))
        response = bytes([Opcode.LL_UNKNOWN_RSP, Opcode.LL_VERSION_IND])
    elif invalid == 'wrong-length':
        response += b'\x00'
    header = (LlId.START if invalid == 'wrong-llid' else LlId.CONTROL) | PDU_DATA_SN_MASK
    connection.accept(bytes([header, len(response)]) + response, True)
    assert connection.closed
    assert (
        connection.link.listener.controller.events[-1].reason
        == ErrorCode.CONNECTION_TERMINATED_DUE_TO_MIC_FAILURE_ERROR
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['plaintext', 'encrypted', 'bad-mic'])
async def test_delayed_unknown_rsp_with_a_key_preserves_encryption_handshake(connection, mode):
    encryption = await _start_encryption_after_phy_request(connection)
    encryption.supply_key(KEY)
    await connection.send(0, connection.radio.now_us + 100)
    header = LlId.CONTROL | PDU_DATA_SN_MASK
    response = bytes([Opcode.LL_UNKNOWN_RSP, Opcode.LL_PHY_REQ])
    if mode != 'plaintext':
        connection.accept(bytes([LlId.CONTINUATION | PDU_DATA_SN_MASK, 0]), True)
        await connection.send(0, connection.radio.now_us + 100)
        assert connection.radio.sent[-1][2][PDU_HEADER_SIZE:] == bytes([Opcode.LL_START_ENC_REQ])
        header = LlId.CONTROL | PDU_DATA_NESN_MASK
        peer = PacketCipher(
            crypto.e(KEY, encryption.skd_c + encryption.skd_p)[::-1],
            encryption.iv_c + encryption.iv_p,
            central=True,
        )
        response = peer.encrypt(header, response)
        if mode == 'bad-mic':
            response = response[:-1] + bytes([response[-1] ^ 1])
    deadline = encryption.deadline_us
    connection.accept(bytes([header, len(response)]) + response, True)
    if mode == 'bad-mic':
        assert connection.closed and connection.pending is not None
        assert connection.controls.phy_request
        assert (
            connection.link.listener.controller.events[-1].reason
            == ErrorCode.CONNECTION_TERMINATED_DUE_TO_MIC_FAILURE_ERROR
        )
    else:
        assert not connection.closed and encryption.state == State.START_RSP
        assert encryption.deadline_us == deadline
        assert not connection.controls.phy_request and connection.controls.deadline_us == 0
        connection.enqueue_acl(False, b'waiting for encrypted START_ENC_RSP')
        await connection.send(0, connection.radio.now_us + 100)
        assert connection.radio.sent[-1][2][PDU_HEADER_SIZE:] == (
            bytes([Opcode.LL_START_ENC_REQ]) if mode == 'plaintext' else b''
        )
