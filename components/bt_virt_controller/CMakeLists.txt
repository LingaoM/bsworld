# Copyright 2026 Xiaomi Corporation
#
# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(hci_virt)

target_sources(app PRIVATE src/main.c)

target_compile_options(native_simulator INTERFACE
  -DHCI_VIRT_IRQ=${CONFIG_HCI_VIRT_IRQ}
  "-I${ZEPHYR_BASE}/boards/native/nrf_bsim/common"
)

# Bottom layer runs in host/runner context and exposes HCI over Unix sockets.
target_sources(native_simulator INTERFACE src/hci_virt_bottom_socket.c)
