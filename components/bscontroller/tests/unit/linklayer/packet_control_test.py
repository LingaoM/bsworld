# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Packet/procedure ownership at the authentication and ACK commit boundary."""

from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest

from bscontroller.linklayer import PDU_DATA_NESN_MASK, ControlOpcode, LlId
from bscontroller.linklayer.connection_parameters import PARAM_REQUEST, UPDATE
from bscontroller.linklayer.procedure import ProcedureOrigin, ProcedurePhase
from bscontroller.radio.base import Phy


@pytest.mark.asyncio
async def test_rejected_receive_observes_ack_without_consuming_pending_tx(connection):
    connection.controls.phy.request_phy(1, 1)
    await connection.send(0, 100)
    pending, ciphertext = connection.event.pending, connection.event.pending_wire
    observed = []

    def reject(context):
        observed.append(context)
        assert connection.event.pending is pending
        assert connection.event.sent_pending
        return None

    connection.event.control = SimpleNamespace(receive=reject)
    response = bytes([ControlOpcode.LL_PHY_RSP, 1, 1])
    header = LlId.CONTROL | PDU_DATA_NESN_MASK
    connection.accept(bytes([header, len(response)]) + response, True)

    assert len(observed) == 1
    context = observed[0]
    assert context.acknowledged_control == pending.payload
    assert not context.duplicate
    with pytest.raises(FrozenInstanceError):
        context.acknowledged_control = None
    assert connection.event.pending is pending
    assert connection.event.pending_wire == ciphertext
    assert connection.event.tx_sn == 0 and connection.event.sent_pending


def test_timer_release_requires_the_same_procedure_instance(connection):
    phy = connection.controls.phy
    old = phy.begin(ProcedureOrigin.LOCAL)
    timer = connection.llcp.response_timer
    timer.start(old, 100)
    old.finish()
    replacement = phy.begin(ProcedureOrigin.LOCAL)
    timer.start(replacement, 200)
    deadline = timer.deadline_us

    # A delayed completion from the same procedure type has a different owner.
    timer.stop(old)
    assert timer.owner is replacement and timer.deadline_us == deadline
    timer.stop(replacement)
    assert timer.owner is None and timer.deadline_us == 0


@pytest.mark.asyncio
async def test_reply_routing_retains_the_actual_procedure_context(connection):
    connection.controls.phy.request_phy(1, 1)
    context = connection.controls.phy.context
    assert context.origin == ProcedureOrigin.LOCAL
    await connection.send(0, 100)
    assert connection.llcp.local_exchanges[ControlOpcode.LL_PHY_REQ] is context
    assert context.transmitted
    connection.control(bytes([ControlOpcode.LL_PHY_UPDATE_IND, 0, 0, 0, 0]))
    assert context.phase == ProcedurePhase.COMPLETE
    assert not connection.llcp.local_exchanges


@pytest.mark.parametrize('origin', list(ProcedureOrigin))
@pytest.mark.parametrize('counter', [0, 0xFFFF])
def test_phy_update_at_current_instant_does_not_reactivate_its_context(
    connection, origin, counter
):
    connection.event_counter = counter
    controls = connection.controls
    if origin == ProcedureOrigin.LOCAL:
        controls.phy.request_phy(2, 2)
    else:
        connection.control(bytes([ControlOpcode.LL_PHY_REQ, 2, 2]))
    context = controls.phy.context
    connection.control(
        bytes([ControlOpcode.LL_PHY_UPDATE_IND, 2, 2]) + counter.to_bytes(2, 'little')
    )

    assert connection.tx_phy == connection.rx_phy == Phy.LE_2M
    assert context.phase == ProcedurePhase.COMPLETE
    assert controls.pending is None and not controls.busy
    assert controls.deadline_us == 0


@pytest.mark.parametrize('origin', list(ProcedureOrigin))
def test_parameter_update_at_current_instant_keeps_context_complete(connection, origin):
    controls = connection.controls
    parameters = controls.connection_parameters
    if origin == ProcedureOrigin.LOCAL:
        controls.connection_parameters.request_parameters(30, 30, 0, 100)
        context = parameters.local_context
    else:
        connection.control(
            bytes([ControlOpcode.LL_CONNECTION_PARAM_REQ])
            + PARAM_REQUEST.pack(30, 30, 0, 100, 0, 0, *([0xFFFF] * 6))
        )
        controls.connection_parameters.reply_parameters(30, 30, 0, 100)
        context = parameters.remote_context
    connection.control(
        bytes([ControlOpcode.LL_CONNECTION_UPDATE_IND])
        + UPDATE.pack(1, 0, 30, 0, 100, connection.event_counter)
    )

    assert connection.parameters.interval == 30
    assert context.phase == ProcedurePhase.COMPLETE
    assert controls.pending is None and not controls.busy
    assert controls.deadline_us == 0
