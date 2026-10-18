# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Standalone Bluetooth LE radio Controller and synchronized runtime."""

from importlib.metadata import PackageNotFoundError, version

from . import hci
from .radio.base import Phy, Radio, Received
from .runtime.event_loop import RadioEventLoop
from .runtime.session import BabbleSimSession as RadioSession
from .runtime.worker import RadioControllerWorker as RadioController

try:
    __version__ = version('bscontroller')
except PackageNotFoundError:
    __version__ = '0+unknown'

__all__ = ['Phy', 'Radio', 'RadioController', 'RadioEventLoop', 'RadioSession', 'Received', 'hci']
