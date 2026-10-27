# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Address privacy state and clocks (Core Vol 6, Part B, 1.3.2 and 4.7)."""

import random
from types import SimpleNamespace

import pytest

from bscontroller.address import Address, AddressType
from bscontroller.errors import ErrorCode
from bscontroller.linklayer.privacy import Privacy, address_hash, resolves

PEER = Address('C0:11:22:33:44:55')
PEER_IRK = bytes.fromhex('ec0234a357c8ad05341010a60a397d9b')[::-1]
LOCAL_IRK = bytes.fromhex('00112233445566778899aabbccddeeff')


@pytest.fixture
def privacy():
    link = SimpleNamespace(
        random=random.Random(19),
        now_us=0,
        config=SimpleNamespace(resolving_list_size=2),
        advertisers={},
        scan=None,
        initiating=None,
        sync=None,
    )
    return Privacy(link)


def test_core_ah_vector():
    """The ah function reproduces the spec sample and drives RPA resolution.

    Purpose: Verify ``address_hash`` against the sample data ah(IRK, 0x708194)
    = 0x0dfbaa and that ``resolves`` accepts the resulting RPA only with the
    right IRK and a random address type (Vol 3, Part H, D.7).

    Steps:
        1. Compute ``address_hash`` with the sample IRK and prand 0x708194.
        2. Build an RPA from the hash and prand.
        3. Resolve it with the sample IRK, with an all-zero IRK, and as a
           public address with the sample IRK.

    Expected:
        - The hash is 0x0dfbaa.
        - Only the sample IRK resolves the random-typed address.
    """
    prand = bytes.fromhex('708194')[::-1]
    hashed = address_hash(PEER_IRK, prand)
    assert hashed == bytes.fromhex('0dfbaa')[::-1]
    address = Address(hashed + prand)
    assert resolves(address, PEER_IRK)
    assert not resolves(address, bytes(16))
    assert not resolves(Address(bytes(address), AddressType.PUBLIC_DEVICE), PEER_IRK)


@pytest.mark.parametrize(
    'address,status',
    [
        ('C0:11:22:33:44:55', ErrorCode.SUCCESS),
        ('40:11:22:33:44:55', ErrorCode.INVALID_COMMAND_PARAMETERS_ERROR),
        ('00:11:22:33:44:55', ErrorCode.INVALID_COMMAND_PARAMETERS_ERROR),
        ('80:11:22:33:44:55', ErrorCode.INVALID_COMMAND_PARAMETERS_ERROR),
    ],
    ids=['static', 'resolvable', 'non-resolvable', 'reserved'],
)
def test_random_identity_must_be_static(privacy, address, status):
    """A random identity address must be a static device address.

    Purpose: Verify that adding a random identity whose two most significant
    bits are not 0b11 returns Invalid HCI Command Parameters (Vol 4, Part E,
    7.8.38; Vol 6, Part B, 1.3.2, Table 1.2).

    Steps:
        1. Add the parametrized random identity with the peer and local IRKs.

    Expected:
        - A static address is added; resolvable, non-resolvable and reserved
          sub-types return 0x12 and leave the list empty.
    """
    identity = Address(address, AddressType.RANDOM_DEVICE)
    assert privacy.add(identity, PEER_IRK, LOCAL_IRK) == status
    assert (privacy.remove(identity) == ErrorCode.SUCCESS) == (status == 0)


def test_capacity_duplicates_and_removal(privacy):
    """The resolving list enforces capacity, unique IRKs and known entries.

    Purpose: Verify resolving-list add, remove and clear status codes for a
    list of two entries (Vol 4, Part E, 7.8.38-7.8.40).

    Steps:
        1. Add the peer with its IRK.
        2. Add a second identity with the same peer IRK, then remove it.
        3. Add the second identity with all-zero IRKs.
        4. Add a third identity.
        5. Remove the peer, clear the list, then remove the second identity.

    Expected:
        - Step 1 succeeds; the duplicate IRK is rejected and its removal
          returns Unknown Connection Identifier.
        - Step 3 succeeds; step 4 returns Memory Capacity Exceeded.
        - Removing the peer and clearing succeed; removing the second identity
          after the clear returns Unknown Connection Identifier.
    """
    assert privacy.add(PEER, PEER_IRK, LOCAL_IRK) == 0
    other = Address('C0:11:22:33:44:66')
    assert privacy.add(other, PEER_IRK, LOCAL_IRK) != 0
    assert privacy.remove(other) == ErrorCode.UNKNOWN_CONNECTION_IDENTIFIER_ERROR
    assert privacy.add(other, bytes(16), bytes(16)) == 0
    assert privacy.add(Address('C0:11:22:33:44:77'), bytes(16), bytes(16)) == 7
    assert privacy.remove(PEER) == 0
    assert privacy.remove(None) == 0
    assert privacy.remove(other) == 2


def test_resolve_mode_and_disable_are_independent(privacy):
    """Privacy mode and address resolution enable act independently.

    Purpose: Verify that Network Privacy Mode rejects a peer's identity address
    even while address resolution is disabled, and that RPAs resolve only
    while resolution is enabled, in either privacy mode (Vol 4, Part E,
    7.8.44, 7.8.77; Vol 6, Part B, 4.7).

    Steps:
        1. Add the peer with its IRK; look up its identity address.
        2. Set Device Privacy Mode; look up the identity and a peer RPA.
        3. Enable address resolution; look up the RPA.
        4. Set Network Privacy Mode; look up the RPA and the identity.
        5. Disable address resolution; look up the RPA.

    Expected:
        - Step 1 rejects the identity; step 2 accepts it and keeps the RPA as
          an unresolved random device address.
        - Step 3 resolves the RPA to the peer as a random identity address.
        - Step 4 still resolves the RPA but rejects the identity.
        - Step 5 returns the RPA unchanged.
    """
    privacy.add(PEER, PEER_IRK, LOCAL_IRK)
    # Network privacy rejects the identity even while resolution is disabled.
    assert privacy.identity(PEER) is None
    assert privacy.set_mode(PEER, 1) == 0
    assert privacy.identity(PEER) == PEER
    rpa = privacy._generate(PEER_IRK)
    assert privacy.identity(rpa).address_type == AddressType.RANDOM_DEVICE
    privacy.set_enabled(1)
    resolved = privacy.identity(rpa)
    assert resolved == PEER and resolved.address_type == AddressType.RANDOM_IDENTITY
    privacy.set_mode(PEER, 0)
    assert privacy.identity(rpa) == PEER
    assert privacy.identity(PEER) is None
    privacy.set_enabled(0)
    assert privacy.identity(rpa) == rpa


def test_rpa_lifetime_and_reset(privacy):
    """Local RPAs persist within the timeout, then renew; reset clears state.

    Purpose: Verify that a generated local RPA is kept until the RPA timeout
    expires and then replaced, and that reset restores the default state and
    timeout range (Vol 4, Part E, 7.8.45; Vol 6, Part B, 1.3.2).

    Steps:
        1. Add the peer with a local IRK and set the RPA timeout to 1-2 s.
        2. Select a local RPA for the peer and read it back.
        3. Select it again at 999,999 us and at 2,000,000 us.
        4. Reset the privacy state.

    Expected:
        - The RPA resolves with the local IRK and is reported by read.
        - It is unchanged at 999,999 us and renewed at 2 s, still resolving
          with the local IRK.
        - After reset, resolution is disabled, reading the peer's RPA returns
          Unknown Connection Identifier and the timeout range is 480-900 s.
    """
    privacy.add(PEER, PEER_IRK, LOCAL_IRK)
    assert privacy.set_timeout(1, 2) == 0
    address = privacy.local_address(2, Address.ANY, PEER)
    assert resolves(address, LOCAL_IRK)
    assert privacy.read_rpa(PEER, local=True) == (0, address)
    privacy.link.now_us = 999_999
    assert privacy.local_address(2, Address.ANY, PEER) == address
    privacy.link.now_us = 2_000_000
    renewed = privacy.local_address(2, Address.ANY, PEER)
    assert renewed != address and resolves(renewed, LOCAL_IRK)
    privacy.reset()
    assert not privacy.enabled
    assert privacy.read_rpa(PEER, local=True)[0] == 2
    assert (privacy.minimum_timeout_s, privacy.maximum_timeout_s) == (480, 900)


def test_target_must_resolve_with_same_records_local_irk(privacy):
    """A directed TargetA must resolve with the advertiser's record local IRK.

    Purpose: Verify that a TargetA RPA is accepted only when it resolves with
    the local IRK of the resolving-list record matching the peer's RPA, and
    only while address resolution is enabled (Vol 6, Part B, 4.7).

    Steps:
        1. Add the peer and enable address resolution.
        2. Generate a peer RPA and a TargetA from the record's local IRK.
        3. Check that TargetA against the peer RPA, then a TargetA generated
           from an unrelated IRK.
        4. Disable address resolution and check the first TargetA again.

    Expected:
        - Only the TargetA from the record's local IRK is accepted.
        - It is rejected once address resolution is disabled.
    """
    privacy.add(PEER, PEER_IRK, LOCAL_IRK)
    privacy.set_enabled(1)
    peer_rpa = privacy._generate(PEER_IRK)
    target = privacy._generate(LOCAL_IRK)
    assert privacy.accept_target(target, Address.ANY, peer_rpa)
    assert not privacy.accept_target(
        privacy._generate(bytes(range(16))), Address.ANY, peer_rpa
    )
    privacy.set_enabled(0)
    assert not privacy.accept_target(target, Address.ANY, peer_rpa)


@pytest.mark.parametrize('role', ['advertising', 'scan', 'initiating', 'sync'])
def test_resolver_command_exclusion(privacy, role):
    """Resolving-list commands are disallowed while a privacy role is active.

    Purpose: Verify that address resolution enable, resolving-list add and
    clear, and Set Privacy Mode return Command Disallowed while advertising,
    scanning, initiating or a pending periodic sync is active (Vol 4, Part E,
    7.8.38, 7.8.40, 7.8.44, 7.8.77).

    Steps:
        1. Add the peer to the resolving list.
        2. Make the parametrized role active.
        3. Enable address resolution while it is disabled.
        4. Mark resolution enabled; add, clear and set privacy mode.

    Expected:
        - Every command returns Command Disallowed, including step 3.
    """
    privacy.add(PEER, PEER_IRK, LOCAL_IRK)
    if role == 'advertising':
        privacy.link.advertisers[0] = SimpleNamespace(enabled=True)
    elif role == 'sync':
        privacy.link.sync = SimpleNamespace(established=False)
    else:
        setattr(privacy.link, role, object())
    # Set Enable is excluded even if resolution is currently disabled.
    assert privacy.set_enabled(1) == ErrorCode.COMMAND_DISALLOWED_ERROR
    privacy.enabled = True
    assert privacy.add(PEER, PEER_IRK, LOCAL_IRK) == 0x0C
    assert privacy.remove(None) == 0x0C
    assert privacy.set_mode(PEER, 1) == 0x0C


def test_established_periodic_sync_does_not_lock_list(privacy):
    """An established periodic sync does not lock the resolving list.

    Purpose: Verify that only a pending periodic sync blocks resolver commands;
    an established sync does not (Vol 4, Part E, 7.8.38, 7.8.44).

    Steps:
        1. Mark a periodic sync as established.
        2. Enable address resolution and add the peer.

    Expected:
        - Both commands succeed.
    """
    privacy.link.sync = SimpleNamespace(established=True)
    assert privacy.set_enabled(1) == 0
    assert privacy.add(PEER, PEER_IRK, LOCAL_IRK) == 0


@pytest.mark.parametrize('minimum,maximum', [(0, 1), (2, 1), (1, 3601)])
def test_invalid_timeout_preserves_previous_range(privacy, minimum, maximum):
    """An invalid RPA timeout range is rejected and the old range is kept.

    Purpose: Verify that an RPA timeout with a zero minimum, a minimum above
    the maximum, or a maximum above 3600 s is rejected (Vol 4, Part E, 7.8.45).

    Steps:
        1. Set the parametrized timeout range.

    Expected:
        - The command returns Invalid HCI Command Parameters.
        - The range stays at the 480-900 s default.
    """
    assert privacy.set_timeout(minimum, maximum) == 0x12
    assert (privacy.minimum_timeout_s, privacy.maximum_timeout_s) == (480, 900)


def test_read_rpa_does_not_expose_a_mutable_cached_address(privacy):
    """Reading an RPA returns a copy, not the cached address.

    Purpose: Verify that mutating the address returned by a local RPA read does
    not change the cached RPA (Vol 4, Part E, 7.8.43).

    Steps:
        1. Add the peer and generate a local RPA.
        2. Read the local RPA and overwrite the returned address bytes.
        3. Read the local RPA again.

    Expected:
        - The first read succeeds.
        - The second read still returns the generated RPA.
    """
    privacy.add(PEER, PEER_IRK, LOCAL_IRK)
    generated = privacy.local_address(2, Address.ANY, PEER)
    status, observed = privacy.read_rpa(PEER, local=True)
    assert status == 0
    observed.address_bytes = bytes(6)
    assert privacy.read_rpa(PEER, local=True)[1] == generated


def test_address_selection_retains_generation_provenance(privacy):
    """Local address selection reports whether the Controller generated it.

    Purpose: Verify that selecting a local address marks an RPA chosen for
    Own_Address_Type 2 as generated and a Host-supplied address with identical
    bits as not generated, so only generated RPAs are reported as local RPAs
    (Vol 4, Part E, 7.7.65.10).

    Steps:
        1. Add the peer and select a local address with Own_Address_Type 2.
        2. Select with Own_Address_Type 1 and the RPA from step 1 as fallback.

    Expected:
        - Step 1 returns a generated RPA resolving with the local IRK.
        - Step 2 returns the same address marked as not generated.
    """
    privacy.add(PEER, PEER_IRK, LOCAL_IRK)
    address, generated = privacy.select_local_address(2, Address.ANY, PEER)
    assert generated and resolves(address, LOCAL_IRK)
    # Identical bits supplied by the Host still use a non-generated address.
    assert privacy.select_local_address(1, address, PEER) == (address, False)
