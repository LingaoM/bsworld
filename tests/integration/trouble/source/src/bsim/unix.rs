// SPDX-License-Identifier: MIT OR Apache-2.0

//! H4 over Unix streams, reusing `bt-hci-serial` for packet framing.

use std::cell::RefCell;
use std::future::poll_fn;
use std::io::{self, Read, Write};
use std::os::fd::AsRawFd;
use std::os::unix::net::UnixStream;
use std::path::Path;
use std::rc::{Rc, Weak};
use std::task::Poll;

use bt_hci_serial::SerialTransport;
use embassy_sync::blocking_mutex::raw::NoopRawMutex;
use embassy_sync::waitqueue::WakerRegistration;

/// Standard H4 framing over the executor's nonblocking Unix stream.
pub type UnixTransport = SerialTransport<NoopRawMutex, Reader, Writer>;

struct Socket {
    stream: UnixStream,
    reader: RefCell<WakerRegistration>,
    writer: RefCell<WakerRegistration>,
}

/// Read half of an executor-owned HCI socket.
pub struct Reader(Rc<Socket>);

/// Write half of an executor-owned HCI socket.
pub struct Writer(Rc<Socket>);

impl embedded_io::ErrorType for Reader {
    type Error = io::Error;
}

impl embedded_io::ErrorType for Writer {
    type Error = io::Error;
}

impl embedded_io_async::Read for Reader {
    async fn read(&mut self, buf: &mut [u8]) -> io::Result<usize> {
        poll_fn(|cx| match (&self.0.stream).read(buf) {
            Err(error) if error.kind() == io::ErrorKind::WouldBlock => {
                self.0.reader.borrow_mut().register(cx.waker());
                Poll::Pending
            }
            Err(error) if error.kind() == io::ErrorKind::Interrupted => {
                cx.waker().wake_by_ref();
                Poll::Pending
            }
            result => Poll::Ready(result),
        })
        .await
    }
}

impl embedded_io_async::Write for Writer {
    async fn write(&mut self, buf: &[u8]) -> io::Result<usize> {
        poll_fn(|cx| match (&self.0.stream).write(buf) {
            Err(error) if error.kind() == io::ErrorKind::WouldBlock => {
                self.0.writer.borrow_mut().register(cx.waker());
                Poll::Pending
            }
            Err(error) if error.kind() == io::ErrorKind::Interrupted => {
                cx.waker().wake_by_ref();
                Poll::Pending
            }
            result => Poll::Ready(result),
        })
        .await
    }

    async fn flush(&mut self) -> io::Result<()> {
        Ok(())
    }
}

#[derive(Default)]
pub(crate) struct Reactor(RefCell<Vec<Weak<Socket>>>);

impl Reactor {
    pub fn connect(&self, path: &Path) -> io::Result<UnixTransport> {
        let stream = UnixStream::connect(path)?;
        stream.set_nonblocking(true)?;
        let socket = Rc::new(Socket {
            stream,
            reader: RefCell::new(WakerRegistration::new()),
            writer: RefCell::new(WakerRegistration::new()),
        });
        self.0.borrow_mut().push(Rc::downgrade(&socket));
        Ok(SerialTransport::new(Reader(socket.clone()), Writer(socket)))
    }

    pub fn poll(&self) -> io::Result<()> {
        let mut sockets = self.0.borrow_mut();
        sockets.retain(|socket| socket.strong_count() != 0);
        for socket in sockets.iter().filter_map(Weak::upgrade) {
            let mut fd = libc::pollfd {
                fd: socket.stream.as_raw_fd(),
                events: if socket.reader.borrow().occupied() {
                    libc::POLLIN
                } else {
                    0
                } | if socket.writer.borrow().occupied() {
                    libc::POLLOUT
                } else {
                    0
                },
                revents: 0,
            };
            // SAFETY: fd points to one initialized pollfd for the duration of poll.
            if unsafe { libc::poll(&mut fd, 1, 0) } < 0 {
                let error = io::Error::last_os_error();
                if error.kind() == io::ErrorKind::Interrupted {
                    continue;
                }
                return Err(error);
            }
            let failed = fd.revents & (libc::POLLERR | libc::POLLHUP | libc::POLLNVAL) != 0;
            if failed || fd.revents & libc::POLLIN != 0 {
                socket.reader.borrow_mut().wake();
            }
            if failed || fd.revents & libc::POLLOUT != 0 {
                socket.writer.borrow_mut().wake();
            }
        }
        Ok(())
    }
}
