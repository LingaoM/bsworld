// SPDX-License-Identifier: MIT OR Apache-2.0

//! BabbleSim FIFO clock participant. No simulated radio is needed in the Host.

use std::fs::{self, File, OpenOptions};
use std::io::{self, Read, Write};
use std::os::fd::AsRawFd;
use std::os::unix::fs::{FileTypeExt, OpenOptionsExt};
use std::path::{Path, PathBuf};
use std::thread;
use std::time::{Duration, Instant};

use super::Clock;

const WAIT: u32 = 0x01;
const WAIT_END: u32 = 0x81;
const DISCONNECT: u32 = 0xffff;
const STARTUP_TIMEOUT: Duration = Duration::from_secs(30);

/// A Host participating directly in BabbleSim's device scheduling protocol.
///
/// After the handshake the FIFOs are blocking: each wait is one atomic
/// 12-byte write (below `PIPE_BUF`) and one 4-byte read. A PHY that exits
/// surfaces as EOF or EPIPE; a PHY that stalls is left to the test harness,
/// which owns the wall-clock timeout and terminates every participant.
pub struct BabbleSim {
    now_us: u64,
    reader: File,
    writer: File,
    lock: PathBuf,
}

impl BabbleSim {
    /// Register a reserved device ID and open its PHY FIFOs.
    /// `sim_dir` is BabbleSim's existing simulation directory, normally
    /// `/tmp/bs_USER/SIM_ID`; `phy_id` is normally `2G4`.
    /// Wall time is used only to bound how long the PHY may take to start.
    pub fn connect(sim_dir: impl AsRef<Path>, phy_id: &str, dev_id: u32) -> io::Result<Self> {
        if phy_id.is_empty() || phy_id.contains('/') {
            return Err(io::Error::new(io::ErrorKind::InvalidInput, "invalid PHY id"));
        }
        let path = |suffix| sim_dir.as_ref().join(format!("{phy_id}.d{dev_id}.{suffix}"));
        let lock = path("lock");
        register(&lock)?;
        let fifos = open_fifos(&path("ptd"), &path("dtp"));
        match fifos {
            Ok((reader, writer)) => Ok(Self {
                now_us: 0,
                reader,
                writer,
                lock,
            }),
            Err(error) => {
                let _ = fs::remove_file(&lock);
                Err(error)
            }
        }
    }
}

impl Clock for BabbleSim {
    fn now_us(&self) -> u64 {
        self.now_us
    }

    fn wait_until(&mut self, target_us: u64) -> io::Result<()> {
        if target_us < self.now_us || target_us == u64::MAX {
            return Err(io::Error::new(io::ErrorKind::InvalidInput, "invalid PHY wait target"));
        }
        // BabbleSim uses native-endian uint32 headers followed by packed uint64 times.
        let mut request = [0; 12];
        request[..4].copy_from_slice(&WAIT.to_ne_bytes());
        request[4..].copy_from_slice(&target_us.to_ne_bytes());
        self.writer.write_all(&request)?;
        let mut response = [0; 4];
        self.reader
            .read_exact(&mut response)
            .map_err(|error| match error.kind() {
                io::ErrorKind::UnexpectedEof => io::Error::new(io::ErrorKind::UnexpectedEof, "PHY disconnected"),
                _ => error,
            })?;
        match u32::from_ne_bytes(response) {
            WAIT_END => self.now_us = target_us,
            DISCONNECT => return Err(io::Error::new(io::ErrorKind::BrokenPipe, "PHY disconnected")),
            _ => return Err(io::Error::new(io::ErrorKind::InvalidData, "invalid PHY wait response")),
        }
        Ok(())
    }
}

impl Drop for BabbleSim {
    fn drop(&mut self) {
        let _ = self.writer.write(&DISCONNECT.to_ne_bytes());
        let _ = fs::remove_file(&self.lock);
    }
}

/// Create the device lock with the PID and start time BabbleSim validates.
fn register(lock: &Path) -> io::Result<()> {
    let mut registration = OpenOptions::new().write(true).create_new(true).open(lock)?;
    let result = (|| {
        let stat = fs::read_to_string("/proc/self/stat")?;
        let start = stat
            .rsplit_once(')')
            .and_then(|(_, fields)| fields.split_whitespace().nth(19))
            .ok_or_else(|| io::Error::other("invalid process start time"))?;
        writeln!(registration, "{}\n{start}", std::process::id())
    })();
    if result.is_err() {
        let _ = fs::remove_file(lock);
    }
    result
}

/// Open both FIFOs in BabbleSim's device order, waiting for the PHY to create
/// them (ENOENT) and to open its read end of `dtp` (ENXIO).
fn open_fifos(ptd: &Path, dtp: &Path) -> io::Result<(File, File)> {
    let deadline = Instant::now() + STARTUP_TIMEOUT;
    let mut reader = None;
    loop {
        let result = (|| {
            if reader.is_none() {
                reader = Some(open_fifo(ptd, false)?);
            }
            open_fifo(dtp, true)
        })();
        match result {
            Ok(writer) => return Ok((reader.unwrap(), writer)),
            Err(error) if matches!(error.raw_os_error(), Some(libc::ENOENT | libc::ENXIO)) => {
                if Instant::now() >= deadline {
                    return Err(io::Error::new(io::ErrorKind::TimedOut, "PHY FIFOs did not open"));
                }
                thread::sleep(Duration::from_millis(1));
            }
            Err(error) => return Err(error),
        }
    }
}

/// Open without blocking so a missing PHY peer can be retried, then switch
/// the descriptor to blocking I/O for the scheduling protocol.
fn open_fifo(path: &Path, write: bool) -> io::Result<File> {
    let file = OpenOptions::new()
        .read(!write)
        .write(write)
        .custom_flags(libc::O_NONBLOCK | libc::O_CLOEXEC)
        .open(path)?;
    if !file.metadata()?.file_type().is_fifo() {
        return Err(io::Error::new(io::ErrorKind::InvalidInput, "PHY path is not a FIFO"));
    }
    let fd = file.as_raw_fd();
    // SAFETY: fd is an open descriptor owned by `file` for both calls.
    let flags = unsafe { libc::fcntl(fd, libc::F_GETFL) };
    if flags < 0 || unsafe { libc::fcntl(fd, libc::F_SETFL, flags & !libc::O_NONBLOCK) } < 0 {
        return Err(io::Error::last_os_error());
    }
    Ok(file)
}
