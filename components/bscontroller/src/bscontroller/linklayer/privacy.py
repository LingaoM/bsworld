# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Link Layer address resolution and private-address lifetimes.

Core Vol 6, Part B, 1.3.2.2, 4.7 and 6: resolve before device filtering,
retain network/device privacy independently of address-resolution enable,
and refresh addresses between events rather than during a packet exchange.
"""

from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from bscontroller.address import (
    IRK_SIZE,
    RPA_HASH_SIZE,
    RPA_PRAND_RANDOM_BITS,
    RPA_PRAND_RESOLVABLE_MASK,
    RPA_PRAND_SIZE,
    Address,
    AddressType,
    OwnAddressType,
    PrivacyMode,
)
from bscontroller.errors import ErrorCode

ZERO_IRK = bytes(IRK_SIZE)
RPA_TIMEOUT_MIN_S = 1
RPA_TIMEOUT_MAX_S = 0x0E10
RPA_TIMEOUT_DEFAULT_MIN_S = 8 * 60
RPA_TIMEOUT_DEFAULT_MAX_S = 15 * 60


def address_hash(key: bytes, prand: bytes) -> bytes:
    """SMP ah (Vol 3, Part H, 2.2.2), with HCI little-endian octet strings."""
    encryptor = Cipher(algorithms.AES(key[::-1]), modes.ECB()).encryptor()
    return encryptor.update(bytes(IRK_SIZE - RPA_PRAND_SIZE) + prand[::-1])[
        -RPA_HASH_SIZE:
    ][::-1]


def resolves(address: Address, key: bytes) -> bool:
    return bool(
        address.is_resolvable
        and key != ZERO_IRK
        and address_hash(key, bytes(address)[RPA_HASH_SIZE:])
        == bytes(address)[:RPA_HASH_SIZE]
    )


@dataclass
class ResolvingRecord:
    identity: Address
    peer_irk: bytes
    local_irk: bytes
    privacy_mode: PrivacyMode = PrivacyMode.NETWORK_PRIVACY_MODE
    local_rpa: Address | None = None
    peer_rpa: Address | None = None
    expires_us: int = 0


class Privacy:
    """Own resolving records and clocks; HCI supplies values, never live entries."""

    def __init__(self, link):
        self.link = link
        self.reset()

    def reset(self) -> None:
        self._records: dict[Address, ResolvingRecord] = {}
        self.enabled = False
        # Version 2 support changes the reset range to 8-15 minutes (7.8.45).
        self.minimum_timeout_s = RPA_TIMEOUT_DEFAULT_MIN_S
        self.maximum_timeout_s = RPA_TIMEOUT_DEFAULT_MAX_S

    def in_use(self) -> bool:
        # Vol 4, Part E, 7.8.38-40,44,77: an enabled resolver cannot be edited
        # during advertising, scanning, initiating, or pending sync acquisition.
        return self.enabled and self._discovery_active()

    def _discovery_active(self) -> bool:
        return (
            any(item.enabled for item in self.link.advertisers.values())
            or self.link.scan is not None
            or self.link.initiating is not None
            or (self.link.sync is not None and not self.link.sync.established)
        )

    def add(self, identity: Address, peer_irk: bytes, local_irk: bytes) -> int:
        if self.in_use():
            return ErrorCode.COMMAND_DISALLOWED_ERROR
        if (
            identity.address_type
            not in (AddressType.PUBLIC_DEVICE, AddressType.RANDOM_DEVICE)
            # 7.8.38 (RC): a random identity must be a static address.
            or (identity.is_random and not identity.is_static)
            or len(peer_irk) != IRK_SIZE
            or len(local_irk) != IRK_SIZE
        ):
            return ErrorCode.INVALID_COMMAND_PARAMETERS_ERROR
        if identity in self._records or any(
            peer_irk != ZERO_IRK and entry.peer_irk == peer_irk
            for entry in self._records.values()
        ):
            return ErrorCode.INVALID_COMMAND_PARAMETERS_ERROR
        if len(self._records) >= self.link.config.resolving_list_size:
            return ErrorCode.MEMORY_CAPACITY_EXCEEDED_ERROR
        copied = Address(bytes(identity), identity.address_type)
        self._records[copied] = ResolvingRecord(
            copied, bytes(peer_irk), bytes(local_irk)
        )
        return ErrorCode.SUCCESS

    def remove(self, identity: Address | None) -> int:
        if self.in_use():
            return ErrorCode.COMMAND_DISALLOWED_ERROR
        if identity is None:
            self._records.clear()
        elif identity not in self._records:
            return ErrorCode.UNKNOWN_CONNECTION_IDENTIFIER_ERROR
        else:
            del self._records[identity]
        return ErrorCode.SUCCESS

    def set_enabled(self, value: int) -> int:
        # 7.8.44 prohibits this command during discovery even while disabled.
        if self._discovery_active():
            return ErrorCode.COMMAND_DISALLOWED_ERROR
        if value not in (False, True):
            return ErrorCode.INVALID_COMMAND_PARAMETERS_ERROR
        self.enabled = bool(value)
        return ErrorCode.SUCCESS

    def set_mode(self, identity: Address, mode: int) -> int:
        if self.in_use():
            return ErrorCode.COMMAND_DISALLOWED_ERROR
        if identity.address_type not in (
            AddressType.PUBLIC_DEVICE,
            AddressType.RANDOM_DEVICE,
        ) or mode not in tuple(PrivacyMode):
            return ErrorCode.INVALID_COMMAND_PARAMETERS_ERROR
        if identity not in self._records:
            return ErrorCode.UNKNOWN_CONNECTION_IDENTIFIER_ERROR
        self._records[identity].privacy_mode = PrivacyMode(mode)
        return ErrorCode.SUCCESS

    def set_timeout(self, minimum: int, maximum: int) -> int:
        if not RPA_TIMEOUT_MIN_S <= minimum <= maximum <= RPA_TIMEOUT_MAX_S:
            return ErrorCode.INVALID_COMMAND_PARAMETERS_ERROR
        self.minimum_timeout_s, self.maximum_timeout_s = minimum, maximum
        return ErrorCode.SUCCESS

    def _generate(self, key: bytes) -> Address:
        # The random portion excludes both all-zero and all-one patterns.
        value = (
            self.link.random.randrange(1, (1 << RPA_PRAND_RANDOM_BITS) - 1)
            | RPA_PRAND_RESOLVABLE_MASK
        )
        prand = value.to_bytes(RPA_PRAND_SIZE, 'little')
        return Address(address_hash(key, prand) + prand, AddressType.RANDOM_DEVICE)

    def _refresh(self, entry: ResolvingRecord) -> None:
        if entry.expires_us > self.link.now_us:
            return
        entry.local_rpa = (
            self._generate(entry.local_irk) if entry.local_irk != ZERO_IRK else None
        )
        entry.peer_rpa = (
            self._generate(entry.peer_irk) if entry.peer_irk != ZERO_IRK else None
        )
        entry.expires_us = (
            self.link.now_us
            + self.link.random.randint(self.minimum_timeout_s, self.maximum_timeout_s)
            * 1_000_000
        )

    def _local_record(self, peer: Address | None) -> ResolvingRecord | None:
        return (
            self._records.get(peer)
            if peer is not None
            else next(
                (
                    entry
                    for entry in self._records.values()
                    if entry.local_irk != ZERO_IRK
                ),
                None,
            )
        )

    def address_available(
        self, own_type: int, fallback: Address, peer: Address | None = None
    ) -> bool:
        """Validate a role's fallback without generating or publishing an RPA.

        Only a role with a peer identity has a "matching entry" (Vol 4, Part E,
        7.8.9/56/66). Scanning and list-based initiation pass no peer and so
        always need the fallback (7.8.11/65/66).
        """
        entry = (
            self._records.get(peer)
            if peer is not None and OwnAddressType(own_type).uses_resolvable_address
            else None
        )
        return bool(entry and entry.local_irk != ZERO_IRK) or not (
            fallback.is_random and bytes(fallback) == bytes(6)
        )

    def select_local_address(
        self, own_type: int, fallback: Address, peer: Address | None = None
    ) -> tuple[Address, bool]:
        """Return the wire address and whether it uses a Controller-generated RPA.

        Preserve that decision with the RF exchange; a later timeout or list edit
        must not change the connection-complete event's account of sent bytes.
        """
        entry = (
            self._local_record(peer)
            if OwnAddressType(own_type).uses_resolvable_address
            else None
        )
        if entry is None:
            return fallback, False
        self._refresh(entry)
        return (
            (entry.local_rpa, True)
            if entry.local_rpa is not None
            else (fallback, False)
        )

    def local_address(
        self, own_type: int, fallback: Address, peer: Address | None = None
    ) -> Address:
        return self.select_local_address(own_type, fallback, peer)[0]

    def target_address(self, identity: Address) -> Address:
        entry = self._records.get(identity)
        if entry is None or not self.enabled:
            return identity
        self._refresh(entry)
        return entry.peer_rpa or identity

    def identity(self, address: Address, *, remember=True) -> Address | None:
        """Resolve over-air RPAs or reject identity use forbidden by privacy mode."""
        if address.address_type in (
            AddressType.PUBLIC_IDENTITY,
            AddressType.RANDOM_IDENTITY,
        ):
            return address
        if self.enabled and address.is_resolvable:
            for entry in self._records.values():
                if resolves(address, entry.peer_irk):
                    if remember:
                        entry.peer_rpa = address
                    return Address(
                        bytes(entry.identity),
                        AddressType.RANDOM_IDENTITY
                        if entry.identity.is_random
                        else AddressType.PUBLIC_IDENTITY,
                    )
        entry = self._records.get(address)
        if (
            entry
            and entry.peer_irk != ZERO_IRK
            and entry.privacy_mode == PrivacyMode.NETWORK_PRIVACY_MODE
        ):
            return None
        return address

    def accept_target(self, target: Address, own: Address, peer: Address) -> bool:
        if not target.is_resolvable or not self.enabled:
            return target == own
        identity = self.identity(peer)
        entry = self._records.get(identity) if identity is not None else None
        return bool(resolves(target, entry.local_irk)) if entry else target == own

    def read_rpa(self, identity: Address, *, local: bool) -> tuple[int, Address]:
        entry = self._records.get(identity)
        if entry is None:
            return ErrorCode.UNKNOWN_CONNECTION_IDENTIFIER_ERROR, Address.ANY_RANDOM
        address = entry.local_rpa if local else entry.peer_rpa
        address = address or Address.ANY_RANDOM
        return ErrorCode.SUCCESS, Address(bytes(address), address.address_type)

    def encryption_failed(self, identity: Address) -> None:
        """Discard both cached RPAs after resolved-peer encryption failure (4.7).

        A wrong IRK can accidentally resolve an address. Rotate immediately so
        subsequent advertising cannot keep using that falsely associated pair;
        established connections retain their own over-air address snapshots.
        """
        entry = self._records.get(identity)
        if entry is not None:
            entry.local_rpa = entry.peer_rpa = None
            entry.expires_us = 0
            self._refresh(entry)

    def report_target(self, target: Address, own: Address, peer: Address) -> Address:
        """Retain target-resolution metadata for directed discovery reports.

        Vol 4, Part E, 7.7.65.13 permits the local identity or received TargetA
        for resolved targets; choose the identity and mark unresolved RPAs 0xFE.
        """
        if not target.is_resolvable:
            return target
        if self.enabled and self.accept_target(target, own, peer):
            return Address(
                bytes(own),
                AddressType.RANDOM_IDENTITY
                if own.is_random
                else AddressType.PUBLIC_IDENTITY,
            )
        return Address(bytes(target), AddressType.UNABLE_TO_RESOLVE)
