# Copyright 2021-2025 Google LLC
# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Bluetooth device addresses (Core 6.3, Vol 6, Part B, 1.3).

Address type tags are also encoded at the HCI service boundary.
"""

from __future__ import annotations

from typing import Any, ClassVar, Self

from bscontroller.errors import InvalidArgumentError
from bscontroller.serialization import SpecableEnum


class AddressType(SpecableEnum):
    PUBLIC_DEVICE = 0x00
    RANDOM_DEVICE = 0x01
    PUBLIC_IDENTITY = 0x02
    RANDOM_IDENTITY = 0x03
    # (Directed Only) Address is RPA, but controller cannot resolve.
    UNABLE_TO_RESOLVE = 0xFE
    # (Extended Only) No address.
    ANONYMOUS = 0xFF


class Address:
    '''
    Bluetooth Address (see Bluetooth spec Vol 6, Part B - 1.3 DEVICE ADDRESS)
    NOTE: the address bytes are stored in little-endian byte order here, so
    address[0] is the LSB of the address, address[5] is the MSB.
    '''

    PUBLIC_DEVICE_ADDRESS = AddressType.PUBLIC_DEVICE
    RANDOM_DEVICE_ADDRESS = AddressType.RANDOM_DEVICE
    PUBLIC_IDENTITY_ADDRESS = AddressType.PUBLIC_IDENTITY
    RANDOM_IDENTITY_ADDRESS = AddressType.RANDOM_IDENTITY

    # Type declarations
    NIL: ClassVar[Address]
    ANY: ClassVar[Address]
    ANY_RANDOM: ClassVar[Address]

    # pylint: disable-next=unnecessary-lambda
    ADDRESS_TYPE_SPEC = {'size': 1, 'mapper': lambda x: Address.address_type_name(x)}

    @classmethod
    def address_type_name(cls: type[Self], address_type: int) -> str:
        return AddressType(address_type).name

    @classmethod
    def parse_address(cls: type[Self], data: bytes, offset: int) -> tuple[int, Self]:
        # Fix the type to a default value. This is used for parsing type-less Classic
        # addresses
        return cls.parse_address_with_type(data, offset, Address.PUBLIC_DEVICE_ADDRESS)

    @classmethod
    def parse_random_address(cls: type[Self], data: bytes, offset: int) -> tuple[int, Self]:
        return cls.parse_address_with_type(data, offset, Address.RANDOM_DEVICE_ADDRESS)

    @classmethod
    def parse_address_with_type(
        cls: type[Self], data: bytes, offset: int, address_type: AddressType
    ) -> tuple[int, Self]:
        return offset + 6, cls(data[offset : offset + 6], address_type)

    @classmethod
    def parse_address_preceded_by_type(cls: type[Self], data: bytes, offset: int) -> tuple[int, Self]:
        address_type = AddressType(data[offset - 1])
        return cls.parse_address_with_type(data, offset, address_type)



    def __init__(
        self,
        address: bytes | str,
        address_type: AddressType = RANDOM_DEVICE_ADDRESS,
    ) -> None:
        '''
        Initialize an instance. `address` may be a byte array in little-endian
        format, or a hex string in big-endian format (with optional ':'
        separators between the bytes).
        If the address is a string suffixed with '/P', `address_type` is ignored and
        the type is set to PUBLIC_DEVICE_ADDRESS.
        '''
        if isinstance(address, bytes):
            self.address_bytes = address
        else:
            # Check if there's a '/P' type specifier
            if address.endswith('P'):
                address_type = Address.PUBLIC_DEVICE_ADDRESS
                address = address[:-2]

            if len(address) == 12 + 5:
                # Form with ':' separators
                address = address.replace(':', '')

            self.address_bytes = bytes(reversed(bytes.fromhex(address)))

        if len(self.address_bytes) != 6:
            raise InvalidArgumentError('invalid address length')

        self.address_type = address_type

    @property
    def is_public(self) -> bool:
        return self.address_type in (
            self.PUBLIC_DEVICE_ADDRESS,
            self.PUBLIC_IDENTITY_ADDRESS,
        )

    @property
    def is_random(self) -> bool:
        return not self.is_public

    @property
    def is_resolvable(self) -> bool:
        return self.address_type == self.RANDOM_DEVICE_ADDRESS and (self.address_bytes[5] >> 6 == 1)

    def to_string(self, with_type_qualifier: bool = True) -> str:
        '''
        String representation of the address, MSB first, with an optional type
        qualifier.
        '''
        result = ':'.join([f'{x:02X}' for x in reversed(self.address_bytes)])
        if not with_type_qualifier or not self.is_public:
            return result
        return result + '/P'

    def __bytes__(self) -> bytes:
        return self.address_bytes

    def __hash__(self) -> int:
        return hash(self.address_bytes)

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, Address)
            and self.address_bytes == other.address_bytes
            and self.is_public == other.is_public
        )

    def __str__(self) -> str:
        return self.to_string()

    def __repr__(self) -> str:
        return f'Address({self.to_string(False)}/{self.address_type_name(self.address_type)})'


Address.NIL = Address(b"\xff" * 6, Address.PUBLIC_DEVICE_ADDRESS)
Address.ANY = Address(bytes(6), Address.PUBLIC_DEVICE_ADDRESS)
Address.ANY_RANDOM = Address(bytes(6), Address.RANDOM_DEVICE_ADDRESS)
