/*
 * Copyright 2026 Xiaomi Corporation
 *
 * HCI Unix socket - Expose Zephyr BT Controller without a UART hardware model.
 * Designed for nrf52_bsim: bypasses UART timing simulation entirely.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <stddef.h>
#include <string.h>

#include <soc.h>
#include <zephyr/irq.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/util.h>
#include <zephyr/sys/byteorder.h>
#include <zephyr/net_buf.h>
#include <zephyr/bluetooth/addr.h>
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/controller.h>
#include <zephyr/bluetooth/hci.h>
#include <zephyr/bluetooth/buf.h>
#include <zephyr/bluetooth/hci_raw.h>
#include "hci_virt_bottom.h"

#define H4_CMD 0x01
#define H4_ACL 0x02
#define H4_SCO 0x03
#define H4_EVT 0x04
#define H4_ISO 0x05
#define HCI_SNOOP_MAX_FRAME 512

static K_THREAD_STACK_DEFINE(tx_thread_stack, CONFIG_BT_HCI_TX_STACK_SIZE);
static K_THREAD_STACK_DEFINE(rx_fwd_thread_stack, CONFIG_BT_HCI_TX_STACK_SIZE);
static K_THREAD_STACK_DEFINE(rx_thread_stack, CONFIG_BT_HCI_TX_STACK_SIZE);
static struct k_thread tx_thread_data;
static struct k_thread rx_fwd_thread_data;
static struct k_thread rx_thread_data;
static K_FIFO_DEFINE(tx_queue);  /* Host socket -> bt_send */
static K_FIFO_DEFINE(rx_queue);  /* bt_enable_raw -> host socket */
static K_SEM_DEFINE(rx_ready_sem, 0, 1);

static bool valid_type(uint8_t type)
{
	return (type == H4_CMD) || (type == H4_ACL) || (type == H4_ISO);
}

static int parse_public_addr(const char *str, bt_addr_t *addr)
{
	if (strlen(str) != BT_ADDR_STR_LEN - 1) {
		return -EINVAL;
	}

	for (size_t i = 2; i < BT_ADDR_STR_LEN - 1; i += 3) {
		if (str[i] != ':') {
			return -EINVAL;
		}
	}

	for (size_t i = 0; i < ARRAY_SIZE(addr->val); i++) {
		size_t reverse_i = ARRAY_SIZE(addr->val) - 1 - i;

		if (!hex2bin(&str[i * 3], 2, &addr->val[reverse_i], 1)) {
			return -EINVAL;
		}
	}

	return bt_addr_eq(addr, BT_ADDR_ANY) ? -EINVAL : 0;
}

static int set_public_addr_from_arg(void)
{
	const char *addr_arg = hci_virt_bd_addr();
	bt_addr_t bdaddr;
	int err;

	if (!addr_arg) {
		return 0;
	}

	err = parse_public_addr(addr_arg, &bdaddr);
	if (err) {
		return err;
	}

	bt_ctlr_set_public_addr(bdaddr.val);

	return 0;
}

static uint32_t get_len(const uint8_t *hdr_buf, uint8_t type)
{
	switch (type) {
	case H4_CMD:
		return ((const struct bt_hci_cmd_hdr *)hdr_buf)->param_len;
	case H4_ISO:
		return bt_iso_hdr_len(
			sys_le16_to_cpu(((const struct bt_hci_iso_hdr *)hdr_buf)->len));
	case H4_ACL:
		return sys_le16_to_cpu(((const struct bt_hci_acl_hdr *)hdr_buf)->len);
	default:
		return 0;
	}
}

static int hdr_len(uint8_t type)
{
	switch (type) {
	case H4_CMD:
		return sizeof(struct bt_hci_cmd_hdr);
	case H4_ISO:
		return sizeof(struct bt_hci_iso_hdr);
	case H4_ACL:
		return sizeof(struct bt_hci_acl_hdr);
	default:
		return 0;
	}
}

static void capture_host_frame(uint8_t type, const struct net_buf *buf)
{
	__ASSERT_NO_MSG(buf->len > 0 && buf->data[0] == type);
	hci_virt_btsnoop_capture(buf->data, buf->len, true);
}

static void hci_virt_isr(const void *arg)
{
	ARG_UNUSED(arg);

	k_sem_give(&rx_ready_sem);
}

/* TX thread: Controller -> host socket (rx_queue filled by bt_enable_raw)
 * bt_enable_raw prepends the H4 type byte into buf->data[0], so
 * buf->data already contains a complete H4 frame. */
static void tx_thread(void *p1, void *p2, void *p3)
{
	while (1) {
		struct net_buf *buf = k_fifo_get(&rx_queue, K_FOREVER);

		hci_virt_btsnoop_capture(buf->data, buf->len, false);
		__ASSERT_NO_MSG(hci_virt_write(buf->data, buf->len) > 0);
		net_buf_unref(buf);

		k_yield();
	}
}

/* RX fwd thread: tx_queue -> bt_send (host socket -> Controller) */
static void rx_fwd_thread(void *p1, void *p2, void *p3)
{
	while (1) {
		struct net_buf *buf = k_fifo_get(&tx_queue, K_FOREVER);
		int err = bt_send(buf);

		__ASSERT_NO_MSG(err == 0);
	}
}

/* Main thread: host socket -> tx_queue (non-blocking state machine) */
static void rx_thread(void *p1, void *p2, void *p3)
{
	enum { ST_TYPE, ST_HDR, ST_PAYLOAD } state = ST_TYPE;
	uint8_t type = 0;
	uint8_t hdr_buf[MAX(sizeof(struct bt_hci_cmd_hdr),
			    MAX(sizeof(struct bt_hci_acl_hdr),
				sizeof(struct bt_hci_iso_hdr)))];
	int hlen = 0, hread = 0;
	int payload_len = 0, payload_read = 0;
	struct net_buf *buf = NULL;

	while (1) {
		k_sem_take(&rx_ready_sem, K_FOREVER);

		if (!hci_virt_poll()) {
			continue;
		}

		do {
			if (state == ST_TYPE) {
				long n = hci_virt_read(&type, 1);

				__ASSERT_NO_MSG(n == 1);

				if (!valid_type(type)) {
					continue;
				}
				hlen = hdr_len(type);
				hread = 0;
				state = ST_HDR;

			} else if (state == ST_HDR) {
				long n = hci_virt_read(hdr_buf + hread, hlen - hread);

				__ASSERT_NO_MSG(n > 0);

				hread += (int)n;
				if (hread < hlen) {
					continue;
				}

				buf = bt_buf_get_tx(bt_buf_type_from_h4(type, BT_BUF_OUT),
						    K_FOREVER, NULL, 0);
				if (!buf) {
					state = ST_TYPE;
					continue;
				}
				net_buf_add_mem(buf, hdr_buf, hlen);

				payload_len = (int)get_len(hdr_buf, type);
				payload_read = 0;

				if (payload_len == 0) {
					capture_host_frame(type, buf);
					k_fifo_put(&tx_queue, buf);
					buf = NULL;
					state = ST_TYPE;
				} else if (payload_len > (int)net_buf_tailroom(buf)) {
					net_buf_unref(buf);
					buf = NULL;
					state = ST_TYPE;
				} else {
					state = ST_PAYLOAD;
				}

			} else { /* ST_PAYLOAD */
				long n = hci_virt_read(net_buf_tail(buf) + payload_read,
						      payload_len - payload_read);

				__ASSERT_NO_MSG(n > 0);

				payload_read += (int)n;
				if (payload_read < payload_len) {
					continue;
				}
				buf->len += payload_len;
				capture_host_frame(type, buf);
				k_fifo_put(&tx_queue, buf);
				buf = NULL;
				state = ST_TYPE;
			}
		} while (hci_virt_poll());
	}
}

int main(void)
{
	int err;

	IRQ_CONNECT(HCI_VIRT_IRQ, CONFIG_HCI_VIRT_IRQ_PRIORITY,
		    hci_virt_isr, NULL, 0);
	irq_enable(HCI_VIRT_IRQ);

	err = set_public_addr_from_arg();
	if (err) {
		hci_virt_trace("failed to set controller public address: %d\n", err);
		return err;
	}

	hci_virt_open();

	err = bt_enable_raw(&rx_queue);
	if (err) {
		hci_virt_trace("failed to enable Bluetooth RAW mode: %d\n", err);
		return err;
	}

	k_thread_create(&tx_thread_data, tx_thread_stack,
			K_THREAD_STACK_SIZEOF(tx_thread_stack),
			tx_thread, NULL, NULL, NULL,
			K_PRIO_COOP(7), 0, K_NO_WAIT);
	k_thread_name_set(&tx_thread_data, "HCI socket TX");

	k_thread_create(&rx_fwd_thread_data, rx_fwd_thread_stack,
			K_THREAD_STACK_SIZEOF(rx_fwd_thread_stack),
			rx_fwd_thread, NULL, NULL, NULL,
			K_PRIO_COOP(7), 0, K_NO_WAIT);
	k_thread_name_set(&rx_fwd_thread_data, "HCI socket RX FWD");

	k_thread_create(&rx_thread_data, rx_thread_stack,
			K_THREAD_STACK_SIZEOF(rx_thread_stack),
			rx_thread, NULL, NULL, NULL,
			K_PRIO_COOP(7), 0, K_NO_WAIT);
	k_thread_name_set(&rx_thread_data, "HCI socket RX");

	while (1) {
		k_sleep(K_FOREVER);
	}

	return 0;
}
