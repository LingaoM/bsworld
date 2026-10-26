# Copyright 2021-2025 Google LLC
# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""AES-128 primitive used by the LE Controller.

Core 6.3, Vol 4, Part E, 7.8.22 and Vol 6, Part E.
"""

from cryptography.hazmat.primitives import ciphers
from cryptography.hazmat.primitives.ciphers import algorithms, modes


def e(key: bytes, data: bytes) -> bytes:
    '''
    AES-128 ECB, expecting byte-swapped inputs and producing a byte-swapped output.

    See Bluetooth spec Vol 3, Part H - 2.2.1 Security function e
    '''

    cipher = ciphers.Cipher(algorithms.AES(key[::-1]), modes.ECB())
    encryptor = cipher.encryptor()
    return encryptor.update(data[::-1])[::-1]
