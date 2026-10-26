# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Per-connection LL control routing, pause gates and procedure lifecycle.

The packet executor reports RX and TX acknowledgments here. Individual procedures
own their state transitions; this coordinator routes cross-procedure replies and
aggregates their deadlines (Core Vol 6, Part B, 5.1, 5.2 and 5.3).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from bscontroller.errors import ErrorCode
from bscontroller.linklayer import (
    LL_RESPONSE_TIMEOUT_US,
    PDU_CONTROL_TERMINATE_SIZE,
    PDU_CONTROL_UNKNOWN_RSP_SIZE,
    PDU_DATA_AUTHENTICATED_HEADER_MASK,
    PDU_DATA_LLID_MASK,
    ControlOpcode,
    LlId,
)
from bscontroller.linklayer.control import ControlProcedures
from bscontroller.linklayer.data_length import valid_data_length
from bscontroller.linklayer.encryption import KEY_MISSING_REJECTIONS, Encryption, State
from bscontroller.linklayer.features import LeFeatureMask
from bscontroller.linklayer.parameters import valid_timing
from bscontroller.linklayer.state import Role

if TYPE_CHECKING:
    from bscontroller.linklayer.connection import Connection

SUCCESS = ErrorCode.SUCCESS
DISALLOWED = ErrorCode.COMMAND_DISALLOWED_ERROR
INVALID = ErrorCode.INVALID_COMMAND_PARAMETERS_ERROR


@dataclass
class PreparedProcedure:
    """An admitted operation started after HCI has published Command Status.

    Some procedures complete immediately from cached peer information. Keeping
    admission separate from execution preserves Command Status before completion;
    start consumes the action so a caller cannot accidentally initiate it twice.
    """

    status: int
    action: Callable[[], None] | None = None

    def start(self) -> None:
        action, self.action = self.action, None
        if action is not None:
            action()


Opcode = ControlOpcode

# Core Vol 6, Part B, 5.1: supported PDUs restricted to one sender role.
LL_CONTROL_PDU_SENDER_ROLES: dict[int, Role] = {
    Opcode.LL_CONNECTION_UPDATE_IND: Role.CENTRAL,
    Opcode.LL_CHANNEL_MAP_IND: Role.CENTRAL,
    Opcode.LL_ENC_REQ: Role.CENTRAL,
    Opcode.LL_FEATURE_REQ: Role.CENTRAL,
    Opcode.LL_PAUSE_ENC_REQ: Role.CENTRAL,
    Opcode.LL_PHY_UPDATE_IND: Role.CENTRAL,
    Opcode.LL_ENC_RSP: Role.PERIPHERAL,
    Opcode.LL_START_ENC_REQ: Role.PERIPHERAL,
    Opcode.LL_PERIPHERAL_FEATURE_REQ: Role.PERIPHERAL,
    Opcode.LL_PHY_RSP: Role.PERIPHERAL,
    Opcode.LL_MIN_USED_CHANNELS_IND: Role.PERIPHERAL,
}


@dataclass
class ProcedureResponseTimer:
    """The serialized Instant-related procedure slot's T_PRT, with explicit ownership.

    A collision can hand this slot from a local PHY request to remote connection
    parameters. Completing the rejected PHY must not stop the new owner's timer.
    Queueing a PDU restarts an active timer (Core Vol 6, Part B, 5.2).
    """

    deadline_us: int = 0
    owner: int | None = None

    def start(self, owner: int, now_us: int) -> None:
        self.owner = owner
        self.deadline_us = now_us + LL_RESPONSE_TIMEOUT_US

    def restart(self, now_us: int) -> None:
        if self.deadline_us:
            self.deadline_us = now_us + LL_RESPONSE_TIMEOUT_US

    def stop(self, owner: int | None = None) -> None:
        if owner is None or self.owner is None or self.owner == owner:
            self.deadline_us = 0
            self.owner = None


@dataclass(frozen=True)
class LocalExchange:
    """A transmitted request awaiting a response, retained while encryption pauses
    LLCP.
    """

    request: int
    responses: frozenset[int]
    owner: ControlProcedures | Encryption


CONTROL_RESPONSES = {
    Opcode.LL_FEATURE_REQ: frozenset((Opcode.LL_FEATURE_RSP,)),
    Opcode.LL_PERIPHERAL_FEATURE_REQ: frozenset((Opcode.LL_FEATURE_RSP,)),
    Opcode.LL_VERSION_IND: frozenset((Opcode.LL_VERSION_IND,)),
    Opcode.LL_CONNECTION_PARAM_REQ: frozenset(
        (Opcode.LL_CONNECTION_PARAM_RSP, Opcode.LL_CONNECTION_UPDATE_IND)
    ),
    Opcode.LL_PHY_REQ: frozenset((Opcode.LL_PHY_RSP, Opcode.LL_PHY_UPDATE_IND)),
    Opcode.LL_LENGTH_REQ: frozenset((Opcode.LL_LENGTH_RSP,)),
    Opcode.LL_PING_REQ: frozenset((Opcode.LL_PING_RSP,)),
}


class LlcpCoordinator:
    def __init__(self, connection: Connection):
        self.connection = connection
        self.response_timer = ProcedureResponseTimer()
        self.controls = ControlProcedures(connection, self.response_timer)
        self.encryption = Encryption(connection)
        self.local_exchanges: dict[int, LocalExchange] = {}
        self.enc_rsp_sent = False

    @property
    def next_deadline_us(self) -> int:
        deadlines = [
            value
            for value in (
                self.controls.next_deadline_us,
                self.encryption.next_deadline_us,
            )
            if value
        ]
        return min(deadlines, default=0)

    def can_send(self, llid: int, payload: bytes) -> bool:
        """PDUs allowed while an encryption procedure is in progress (Core Vol 6, Part
        B, 5.1.3.1, 5.1.3.2).
        """
        if not self.encryption.busy:
            return True
        return (
            llid == LlId.CONTROL
            and bool(payload)
            and payload[0]
            in (
                Opcode.LL_ENC_REQ,
                Opcode.LL_ENC_RSP,
                Opcode.LL_START_ENC_REQ,
                Opcode.LL_START_ENC_RSP,
                Opcode.LL_PAUSE_ENC_REQ,
                Opcode.LL_PAUSE_ENC_RSP,
                Opcode.LL_TERMINATE_IND,
                Opcode.LL_REJECT_IND,
                Opcode.LL_REJECT_EXT_IND,
            )
        )

    def prepare(self, payload: bytes) -> bytes:
        return self.controls.prepare(payload)

    def sent(self, payload: bytes, *, first: bool) -> None:
        if first and payload[0] in CONTROL_RESPONSES:
            owner = (
                self.encryption if payload[0] == Opcode.LL_PING_REQ else self.controls
            )
            self.local_exchanges[payload[0]] = LocalExchange(
                payload[0], CONTROL_RESPONSES[payload[0]], owner
            )
        if payload[0] == Opcode.LL_ENC_RSP and self.connection.role == Role.PERIPHERAL:
            self.enc_rsp_sent = True
        if first:
            self.controls.sent(payload)
        self.encryption.sent(payload)
        self._prune_exchanges()

    def acknowledged(self, payload: bytes) -> None:
        self.controls.acknowledge(payload)
        self.encryption.acknowledged(payload)

    def receive(self, header: int, payload: bytes, *, duplicate: bool) -> bytes | None:
        """Authenticate, check cross-procedure admissibility, then permit ACK
        commitment.
        """
        if not payload:
            return payload
        authenticated_header = header & PDU_DATA_AUTHENTICATED_HEADER_MASK
        wire, authenticated = payload, self.encryption.rx_enabled
        payload = self.encryption.decrypt(header, payload, duplicate=duplicate)
        if payload is None:
            return None
        rejection_ack = (
            self.encryption.state == State.REJECT
            and not self.encryption.refresh
            and self.connection.event.acknowledges_control(
                header, KEY_MISSING_REJECTIONS
            )
        )
        # Vol 6, Part B, 5.1.3.1 permits a delayed UNKNOWN_RSP after ENC_RSP for a
        # previously sent Peripheral control PDU. Authenticate first, then let the
        # control handler finish that procedure without releasing the encryption pause.
        delayed_unknown_response = self.permits_delayed_unknown(header, payload)
        # The Central can resume data in the same PDU that acknowledges our rejection.
        # Connection.accept commits the acknowledgment only after validating the whole
        # PDU.
        if (
            not duplicate
            and not rejection_ack
            and not delayed_unknown_response
            and self.encryption.state
            in (
                State.KEY,
                State.START_REQ,
                State.START_RSP,
                State.PAUSE_ACK,
                State.RESTART,
                State.REJECT,
            )
        ):
            expected = {
                State.KEY: Opcode.LL_TERMINATE_IND,
                State.START_REQ: Opcode.LL_START_ENC_REQ,
                State.START_RSP: Opcode.LL_START_ENC_RSP,
                State.PAUSE_ACK: Opcode.LL_PAUSE_ENC_RSP,
                State.RESTART: Opcode.LL_ENC_REQ,
                State.REJECT: Opcode.LL_TERMINATE_IND,
            }[self.encryption.state]
            if header & PDU_DATA_LLID_MASK != LlId.CONTROL or payload[0] not in (
                expected,
                Opcode.LL_TERMINATE_IND,
                Opcode.LL_REJECT_IND,
                Opcode.LL_REJECT_EXT_IND,
            ):
                self.connection.complete(
                    ErrorCode.CONNECTION_TERMINATED_DUE_TO_MIC_FAILURE_ERROR
                )
                return None
        self.encryption.last_received = (
            authenticated_header,
            wire,
            payload,
            authenticated,
        )
        return payload

    def permits_delayed_unknown(self, header: int, payload: bytes) -> bool:
        """A prior Peripheral procedure may answer after ENC_RSP (Vol 6, Part B,
        5.1.3.1).
        """
        return (
            self.connection.role == Role.PERIPHERAL
            and self.enc_rsp_sent
            and self.encryption.state in (State.KEY, State.START_RSP, State.REJECT)
            and header & PDU_DATA_LLID_MASK == LlId.CONTROL
            and len(payload) == PDU_CONTROL_UNKNOWN_RSP_SIZE
            and payload[0] == Opcode.LL_UNKNOWN_RSP
            and payload[1] in self.local_exchanges
        )

    def _prune_exchanges(self) -> None:
        # Legacy rejects carry no request opcode. Let the procedure interpret the
        # rejection, then remove every exchange whose owner has completed it.
        active = {
            Opcode.LL_FEATURE_REQ: self.controls.feature_request,
            Opcode.LL_PERIPHERAL_FEATURE_REQ: self.controls.feature_request,
            Opcode.LL_VERSION_IND: self.controls.version_request,
            Opcode.LL_CONNECTION_PARAM_REQ: self.controls.parameter_request,
            Opcode.LL_PHY_REQ: self.controls.phy_request,
            Opcode.LL_LENGTH_REQ: self.controls.data_length.pending,
            Opcode.LL_PING_REQ: self.encryption.ping_pending,
        }
        self.local_exchanges = {
            opcode: entry
            for opcode, entry in self.local_exchanges.items()
            if active[opcode]
        }

    def event_prepare(self) -> None:
        self.controls.apply()
        self._prune_exchanges()

    def close(self, reason: int) -> None:
        self.controls.finish_features(reason)
        self.controls.finish_version(None)
        self.local_exchanges.clear()
        self.response_timer.stop()

    def check_timeout(self) -> bool:
        return self.controls.check_timeout() or self.encryption.check_timeout()

    def control(self, payload: bytes) -> None:
        """Route control PDUs after packet validation; termination remains always
        available.
        """
        connection = self.connection
        if not payload:
            return
        opcode = payload[0]
        if LL_CONTROL_PDU_SENDER_ROLES.get(opcode) == connection.role:
            connection.enqueue_control(
                bytes([Opcode.LL_UNKNOWN_RSP, opcode]), priority=True
            )
            return
        # Replies belong to the outstanding exchange, including one paused by
        # encryption. Do not make the encryption state machine identify PHY/DLE replies.
        exchange = None
        if opcode == Opcode.LL_UNKNOWN_RSP and len(payload) == 2:
            exchange = self.local_exchanges.get(payload[1])
        elif opcode == Opcode.LL_REJECT_EXT_IND and len(payload) == 3:
            exchange = self.local_exchanges.get(payload[1])
        else:
            exchange = next(
                (
                    entry
                    for entry in self.local_exchanges.values()
                    if opcode in entry.responses
                ),
                None,
            )
        if exchange is not None and exchange.owner.control(payload):
            self.local_exchanges.pop(exchange.request, None)
            return
        if self.encryption.control(payload):
            return
        if self.controls.control(payload):
            self._prune_exchanges()
            return
        if (
            opcode == Opcode.LL_TERMINATE_IND
            and len(payload) == PDU_CONTROL_TERMINATE_SIZE
        ):
            connection.remote_termination = payload[1]
        elif opcode not in (
            Opcode.LL_UNKNOWN_RSP,
            Opcode.LL_FEATURE_RSP,
            Opcode.LL_VERSION_IND,
        ):
            connection.enqueue_control(
                bytes([Opcode.LL_UNKNOWN_RSP, opcode]), priority=True
            )

    def prepare_encryption(
        self, rand: bytes, ediv: int, key: bytes
    ) -> PreparedProcedure:
        if self.connection.role != Role.CENTRAL or self.encryption.busy:
            return PreparedProcedure(DISALLOWED)
        return PreparedProcedure(
            SUCCESS, lambda: self.encryption.start(rand, ediv, key)
        )

    def prepare_features(self) -> PreparedProcedure:
        if self.controls.feature_request:
            return PreparedProcedure(DISALLOWED)
        return PreparedProcedure(SUCCESS, self.controls.request_features)

    def prepare_version(self) -> PreparedProcedure:
        if self.controls.version_request:
            return PreparedProcedure(DISALLOWED)
        return PreparedProcedure(SUCCESS, self.controls.request_version)

    def prepare_phy(
        self, tx: int, rx: int, coding: int, parameter_status: int
    ) -> PreparedProcedure:
        if parameter_status:
            return PreparedProcedure(parameter_status)
        if self.controls.busy:
            return PreparedProcedure(DISALLOWED)

        def start():
            self.connection.tx_coding = coding
            self.controls.request_phy(tx, rx)

        return PreparedProcedure(SUCCESS, start)

    def prepare_parameters(
        self,
        minimum: int,
        maximum: int,
        latency: int,
        timeout: int,
        *,
        valid_ce_lengths: bool,
    ) -> PreparedProcedure:
        if self.controls.busy:
            return PreparedProcedure(DISALLOWED)
        if not valid_timing(minimum, maximum, latency, timeout) or not valid_ce_lengths:
            return PreparedProcedure(INVALID)
        if (
            self.connection.role == Role.PERIPHERAL
            and not self.controls.supports_parameter_request
        ):
            return PreparedProcedure(ErrorCode.UNSUPPORTED_REMOTE_FEATURE_ERROR)

        def start():
            # Only the Central can fall back to UPDATE_IND (Vol 6, Part B, 5.1.1).
            if (
                self.connection.role == Role.CENTRAL
                and not self.controls.supports_parameter_request
            ):
                self.controls.request_update(minimum, latency, timeout)
            else:
                self.controls.request_parameters(minimum, maximum, latency, timeout)

        return PreparedProcedure(SUCCESS, start)

    def supply_key(self, key: bytes | None) -> int:
        if (
            self.connection.role != Role.PERIPHERAL
            or self.encryption.state != State.KEY
        ):
            return DISALLOWED
        self.encryption.supply_key(key)
        return SUCCESS

    def reply_parameters(
        self, minimum: int, maximum: int, latency: int, timeout: int
    ) -> int:
        if self.controls.remote_parameters is None:
            return DISALLOWED
        if not valid_timing(minimum, maximum, latency, timeout):
            return INVALID
        self.controls.reply_parameters(minimum, maximum, latency, timeout)
        return SUCCESS

    def reject_parameters(self, reason: int) -> int:
        if self.controls.remote_parameters is None:
            return DISALLOWED
        self.controls.reject_remote_parameters(reason)
        return SUCCESS

    def set_data_length(self, octets: int, time_us: int) -> int:
        if not valid_data_length(octets, time_us):
            return INVALID
        if self.controls.busy:
            return DISALLOWED
        if (
            self.connection.peer_features is not None
            and not self.connection.peer_features
            & LeFeatureMask.LE_DATA_PACKET_LENGTH_EXTENSION
        ):
            return ErrorCode.UNSUPPORTED_REMOTE_FEATURE_ERROR
        self.controls.data_length.request(octets, time_us)
        return SUCCESS
