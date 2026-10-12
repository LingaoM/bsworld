/*
 * Copyright 2026 Xiaomi Corporation
 *
 * Host/bottom side: exposes HCI over a Unix domain socket.
 * Built in native_simulator runner context.
 * Use -hci-socket=<path> on the command line to specify the socket path,
 * or defaults to /tmp/hci0.sock.
 * Use -btsnoop-socket=<path> to enable best-effort passive BTSnoop capture.
 * Use -bd-addr=<AA:BB:CC:DD:EE:FF> to set the controller public address.
 * Use -hci-poll-interval=<microseconds> to override the default 1 ms HCI poll
 * interval and PHY maximum resynchronization offset.
 *
 * The socket is created as a SOCK_STREAM server; it accepts one client at a
 * time.  If the client disconnects, it waits for a new connection.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>
#include <poll.h>
#include <stdarg.h>
#include <sys/socket.h>
#include <sys/un.h>
#include "irq_ctrl.h"
#include "nsi_hw_scheduler.h"
#include "nsi_hws_models_if.h"
#include <nsi_tracing.h>
#include <nsi_tasks.h>
#include "bs_cmd_line.h"
#include "bs_dynargs.h"
#include "phy_sync_ctrl.h"
#include "hci_virt_bottom.h"

#define DEFAULT_SOCKET_PATH "/tmp/hci0.sock"
#define DEFAULT_HCI_POLL_INTERVAL_US 1000U
#define BTSNOOP_DATALINK_HCI_H4 1002U
#define BTSNOOP_EPOCH_DELTA_US 0x00DCDDB30F2F8000ULL
#define BTSNOOP_FILE_HEADER_LEN 16
#define BTSNOOP_RECORD_HEADER_LEN 24
#define BTSNOOP_MAX_FRAME 2048

#ifndef MSG_NOSIGNAL
#define MSG_NOSIGNAL 0
#endif

static int listen_fd = -1;
static int client_fd = -1;
static int btsnoop_listen_fd = -1;
static int btsnoop_client_fd = -1;
static char *socket_path_arg;
static char *btsnoop_socket_path_arg;
static char *bd_addr_arg;
static uint64_t hci_poll_interval_arg;
static bs_time_t hci_poll_interval_us = DEFAULT_HCI_POLL_INTERVAL_US;
static uint64_t hci_virt_poll_time = NSI_NEVER;
static uint32_t btsnoop_drops;

#if defined(NSI_PRIMARY_MCU_N)
#define HCI_VIRT_SET_IRQ() hw_irq_ctrl_set_irq(NSI_PRIMARY_MCU_N, HCI_VIRT_IRQ)
#else
#define HCI_VIRT_SET_IRQ() hw_irq_ctrl_set_irq(HCI_VIRT_IRQ)
#endif

static void put_be32(uint8_t *dst, uint32_t value)
{
	dst[0] = (uint8_t)(value >> 24);
	dst[1] = (uint8_t)(value >> 16);
	dst[2] = (uint8_t)(value >> 8);
	dst[3] = (uint8_t)value;
}

static void put_be64(uint8_t *dst, uint64_t value)
{
	put_be32(dst, (uint32_t)(value >> 32));
	put_be32(dst + 4, (uint32_t)value);
}

static void set_nonblocking(int fd)
{
	fcntl(fd, F_SETFL, fcntl(fd, F_GETFL) | O_NONBLOCK);
}

static void schedule_poll(bs_time_t delay_us)
{
	hci_virt_poll_time = nsi_hws_get_time() + delay_us;
	nsi_hws_find_next_event();
}

static void hci_virt_poll_event(void)
{
	if (hci_virt_poll()) {
		HCI_VIRT_SET_IRQ();
	}

	schedule_poll(hci_poll_interval_us);
}

/* Run after the priority-900 PHY synchronization event at the same timestamp. */
NSI_HW_EVENT(hci_virt_poll_time, hci_virt_poll_event, 901);

static void configure_hci_poll_interval(char *argv, int offset)
{
	(void)argv;
	(void)offset;

	if (hci_poll_interval_arg == 0 || hci_poll_interval_arg == TIME_NEVER) {
		nsi_print_error_and_exit("hci-poll-interval must be between 1 and %llu microseconds\n",
					 (unsigned long long)(TIME_NEVER - 1));
	}

	hci_poll_interval_us = hci_poll_interval_arg;
}

static void register_socket_args(void)
{
	static bs_args_struct_t opts[] = {
		{
			.option   = "hci-socket",
			.name     = "path",
			.type     = 's',
			.dest     = (void *)&socket_path_arg,
			.descript = "Unix socket path for HCI transport "
				    "(default: " DEFAULT_SOCKET_PATH ")",
		},
		{
			.option   = "btsnoop-socket",
			.name     = "path",
			.type     = 's',
			.dest     = (void *)&btsnoop_socket_path_arg,
			.descript = "Unix socket path for passive BTSnoop HCI capture "
				    "(disabled by default)",
		},
		{
			.option   = "bd-addr",
			.name     = "addr",
			.type     = 's',
			.dest     = (void *)&bd_addr_arg,
			.descript = "controller public address in AA:BB:CC:DD:EE:FF format",
		},
		{
			.option   = "hci-poll-interval",
			.name     = "microseconds",
			.type     = 'U',
			.dest     = (void *)&hci_poll_interval_arg,
			.call_when_found = configure_hci_poll_interval,
			.descript = "HCI socket poll interval and PHY maximum resynchronization "
				    "offset (default: 1000 microseconds)",
		},
		ARG_TABLE_ENDMARKER,
	};

	bs_add_extra_dynargs(opts);
}

NSI_TASK(register_socket_args, PRE_BOOT_1, 1);

void hci_virt_trace(const char *fmt, ...)
{
	va_list ap;

	va_start(ap, fmt);
	nsi_vprint_trace(fmt, ap);
	va_end(ap);
}

static const char *get_path(void)
{
	return (socket_path_arg && socket_path_arg[0]) ? socket_path_arg
						       : DEFAULT_SOCKET_PATH;
}

const char *hci_virt_bd_addr(void)
{
	return (bd_addr_arg && bd_addr_arg[0]) ? bd_addr_arg : NULL;
}

static bool btsnoop_enabled(void)
{
	return btsnoop_socket_path_arg && btsnoop_socket_path_arg[0];
}

static void close_btsnoop_client(void)
{
	if (btsnoop_client_fd >= 0) {
		close(btsnoop_client_fd);
		btsnoop_client_fd = -1;
	}
}

static bool write_nonblocking_all(int fd, const uint8_t *buf, unsigned long len)
{
	unsigned long total = 0;

	while (total < len) {
		long n = send(fd, buf + total, len - total, MSG_NOSIGNAL);

		if (n > 0) {
			total += n;
			continue;
		}

		if (n < 0 && errno == EINTR) {
			continue;
		}

		return false;
	}

	return true;
}

static bool write_btsnoop_file_header(void)
{
	uint8_t header[BTSNOOP_FILE_HEADER_LEN] = {
		'b', 't', 's', 'n', 'o', 'o', 'p', '\0',
	};

	put_be32(&header[8], 1);
	put_be32(&header[12], BTSNOOP_DATALINK_HCI_H4);

	return write_nonblocking_all(btsnoop_client_fd, header, sizeof(header));
}

static void try_accept_btsnoop(void)
{
	int fd;

	if (btsnoop_listen_fd < 0 || btsnoop_client_fd >= 0) {
		return;
	}

	fd = accept(btsnoop_listen_fd, NULL, NULL);
	if (fd >= 0) {
		set_nonblocking(fd);
		btsnoop_client_fd = fd;
		nsi_print_trace("btsnoop_socket: client connected\n");
		if (!write_btsnoop_file_header()) {
			nsi_print_trace("btsnoop_socket: failed to send file header, client disconnected\n");
			close_btsnoop_client();
		}
		return;
	}

	if (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR) {
		return;
	}

	nsi_print_trace("btsnoop_socket: accept failed: %s\n", strerror(errno));
}

static int open_btsnoop_socket(void)
{
	struct sockaddr_un addr = { .sun_family = AF_UNIX };

	if (!btsnoop_enabled()) {
		return 0;
	}

	unlink(btsnoop_socket_path_arg);

	btsnoop_listen_fd = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);
	if (btsnoop_listen_fd < 0) {
		nsi_print_error_and_exit("btsnoop_socket: socket: %s\n", strerror(errno));
	}

	strncpy(addr.sun_path, btsnoop_socket_path_arg, sizeof(addr.sun_path) - 1);
	if (bind(btsnoop_listen_fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
		nsi_print_error_and_exit("btsnoop_socket: bind %s: %s\n",
					 btsnoop_socket_path_arg, strerror(errno));
	}

	if (listen(btsnoop_listen_fd, 1) < 0) {
		nsi_print_error_and_exit("btsnoop_socket: listen: %s\n", strerror(errno));
	}

	set_nonblocking(btsnoop_listen_fd);
	nsi_print_trace("btsnoop_socket: Unix socket = %s\n", btsnoop_socket_path_arg);

	return 0;
}

/* Non-blocking single attempt: returns 1 if accepted, 0 if no client yet */
static int try_accept(void)
{
	client_fd = accept(listen_fd, NULL, NULL);
	if (client_fd >= 0) {
		set_nonblocking(client_fd);
		nsi_print_trace("hci_socket: client connected\n");
		return 1;
	}

	if (errno == EAGAIN || errno == EWOULDBLOCK) {
		return 0;
	}

	nsi_print_error_and_exit("hci_socket: accept: %s\n", strerror(errno));

	return 0;
}

/* Bind and listen only; does NOT block waiting for a client. */
int hci_virt_open(void)
{
	const char *path = get_path();
	struct sockaddr_un addr = { .sun_family = AF_UNIX };

	phy_sync_ctrl_set_max_resync_offset(hci_poll_interval_us);
	unlink(path);

	listen_fd = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);
	if (listen_fd < 0) {
		nsi_print_error_and_exit("hci_socket: socket: %s\n", strerror(errno));
	}

	strncpy(addr.sun_path, path, sizeof(addr.sun_path) - 1);
	if (bind(listen_fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
		nsi_print_error_and_exit("hci_socket: bind %s: %s\n",
					 path, strerror(errno));
	}

	if (listen(listen_fd, 1) < 0) {
		nsi_print_error_and_exit("hci_socket: listen: %s\n", strerror(errno));
	}

	set_nonblocking(listen_fd);
	nsi_print_trace("hci_socket: Unix socket = %s\n", path);
	open_btsnoop_socket();
	schedule_poll(hci_poll_interval_us);

	return 0;
}

/* Returns 1 if data available, 0 if not */
int hci_virt_poll(void)
{
	try_accept_btsnoop();

	if (client_fd < 0) {
		/* Waiting for reconnect; non-blocking try each call */
		try_accept();
		return 0;
	}

	struct pollfd pfd = { .fd = client_fd, .events = POLLIN };
	int rc = poll(&pfd, 1, 0);

	if (rc < 0) {
		return 0;
	}
	if (pfd.revents & (POLLHUP | POLLERR)) {
		nsi_print_trace("hci_socket: client disconnected (POLLHUP/POLLERR)\n");
		close(client_fd);
		client_fd = -1;
		return 0;
	}

	return (rc == 1) ? 1 : 0;
}

/* Non-blocking read: returns bytes read, 0 if no data, -1 on error */
long hci_virt_read(void *buf, unsigned long len)
{
	long n = read(client_fd, buf, len);

	if (n == 0) {
		nsi_print_trace("hci_socket: client disconnected (EOF)\n");
		close(client_fd);
		client_fd = -1;
		return 0;
	}

	if (n < 0) {
		if (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR) {
			return 0;
		}

		return -1;
	}

	return n;
}

long hci_virt_write(const void *buf, unsigned long len)
{
	unsigned long total = 0;
	const uint8_t *p = buf;

	while (total < len) {
		long n = write(client_fd, p + total, len - total);

		if (n < 0) {
			if (errno == EINTR) {
				continue;
			}

			nsi_print_trace("hci_socket: write error (%s), client disconnected\n", strerror(errno));
			close(client_fd);
			client_fd = -1;
			return -1;
		}

		total += n;
	}

	return total;
}

void hci_virt_btsnoop_capture(const void *buf, unsigned long len, bool tx)
{
	uint8_t record[BTSNOOP_RECORD_HEADER_LEN + BTSNOOP_MAX_FRAME];
	const uint8_t *payload = buf;
	uint64_t timestamp_us;
	uint32_t drops;

	if (btsnoop_listen_fd < 0) {
		return;
	}

	try_accept_btsnoop();
	if (btsnoop_client_fd < 0) {
		return;
	}

	if (len > BTSNOOP_MAX_FRAME) {
		btsnoop_drops++;
		return;
	}

	timestamp_us = nsi_hws_get_time() + BTSNOOP_EPOCH_DELTA_US;
	drops = btsnoop_drops;

	put_be32(&record[0], (uint32_t)len);
	put_be32(&record[4], (uint32_t)len);
	put_be32(&record[8], tx ? 0U : 1U);
	put_be32(&record[12], drops);
	put_be64(&record[16], timestamp_us);
	memcpy(&record[BTSNOOP_RECORD_HEADER_LEN], payload, len);

	if (!write_nonblocking_all(btsnoop_client_fd, record,
				   BTSNOOP_RECORD_HEADER_LEN + len)) {
		btsnoop_drops++;
		nsi_print_trace("btsnoop_socket: record write failed, client disconnected\n");
		close_btsnoop_client();
		return;
	}

	btsnoop_drops = 0;
}
