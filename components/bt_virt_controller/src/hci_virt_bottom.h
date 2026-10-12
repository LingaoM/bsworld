/*
 * Copyright 2026 Xiaomi Corporation
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef HCI_VIRT_BOTTOM_H
#define HCI_VIRT_BOTTOM_H

#include <stdbool.h>
#include <stdint.h>

#ifndef HCI_VIRT_IRQ
#ifdef CONFIG_HCI_VIRT_IRQ
#define HCI_VIRT_IRQ CONFIG_HCI_VIRT_IRQ
#else
#define HCI_VIRT_IRQ 30
#endif
#endif

int  hci_virt_open(void);
const char *hci_virt_bd_addr(void);
void hci_virt_trace(const char *fmt, ...);
int  hci_virt_poll(void);
long hci_virt_read(void *buf, unsigned long len);
long hci_virt_write(const void *buf, unsigned long len);
void hci_virt_btsnoop_capture(const void *buf, unsigned long len, bool tx);

#endif /* HCI_VIRT_BOTTOM_H */
