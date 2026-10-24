# Copyright 2021-2025 Google LLC
# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Byte-field serialization support shared by Controller protocol codecs."""

from __future__ import annotations

import dataclasses
import enum
from collections.abc import Callable, Sequence
from typing import Any, Literal


class OpenIntEnum(enum.IntEnum):
    """
    Subclass of enum.IntEnum that can hold integer values outside the set of
    predefined values. This is convenient for implementing protocols where some
    integer constants may be added over time.
    """

    @classmethod
    def _missing_(cls, value):
        if not isinstance(value, int):
            return None

        obj = int.__new__(cls, value)
        obj._value_ = value
        obj._name_ = f"{cls.__name__}[{value}]"
        return obj


class CompatibleIntFlag(enum.IntFlag):
    """Named base for the HCI feature masks, kept as their shared supertype."""


class SpecableEnum(OpenIntEnum):
    @classmethod
    def type_spec(cls, size: int, byteorder: Literal['little', 'big'] = 'little'):
        return {
            'serializer': lambda x: x.to_bytes(size, byteorder),
            'parser': lambda data, offset: (
                offset + size,
                cls(int.from_bytes(data[offset : offset + size], byteorder)),
            ),
            'mapper': lambda x: cls(x).name,
        }

    @classmethod
    def type_metadata(
        cls,
        size: int,
        list_begin: bool = False,
        list_end: bool = False,
        byteorder: Literal['little', 'big'] = 'little',
    ):
        return metadata(
            cls.type_spec(size, byteorder),
            list_begin=list_begin,
            list_end=list_end,
        )


class SpecableFlag(enum.IntFlag):
    @classmethod
    def type_spec(cls, size: int, byteorder: Literal['little', 'big'] = 'little'):
        return {
            'serializer': lambda x: x.to_bytes(size, byteorder),
            'parser': lambda data, offset: (
                offset + size,
                cls(int.from_bytes(data[offset : offset + size], byteorder)),
            ),
            'mapper': lambda x: cls(x).name,
        }

    @classmethod
    def type_metadata(
        cls,
        size: int,
        list_begin: bool = False,
        list_end: bool = False,
        byteorder: Literal['little', 'big'] = 'little',
    ):
        return metadata(
            cls.type_spec(size, byteorder),
            list_begin=list_begin,
            list_end=list_end,
        )


FieldSpec = dict[str, Any] | Callable[[bytes, int], tuple[int, Any]] | str | int
Fields = Sequence['tuple[str, FieldSpec] | Fields']


@dataclasses.dataclass
class FieldMetadata:
    spec: FieldSpec
    list_begin: bool = False
    list_end: bool = False


def metadata(spec: FieldSpec, list_begin: bool = False, list_end: bool = False) -> dict[str, Any]:
    return {"bscontroller.wire": FieldMetadata(spec=spec, list_begin=list_begin, list_end=list_end)}


def bit_flags_to_strings(bits, bit_flag_names):
    names = []
    index = 0
    while bits != 0:
        if bits & 1:
            name = bit_flag_names[index] if index < len(bit_flag_names) else f'#{index}'
            names.append(name)
        bits >>= 1
        index += 1

    return names


def name_or_number(dictionary: dict[int, str], number: int, width: int = 2) -> str:
    name = dictionary.get(number)
    if name is not None:
        return name
    return f'[0x{number:0{width}X}]'


def padded_bytes(buffer, size):
    padding_size = max(size - len(buffer), 0)
    return buffer + bytes(padding_size)
