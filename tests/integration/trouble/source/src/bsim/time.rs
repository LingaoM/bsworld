// SPDX-License-Identifier: MIT OR Apache-2.0

//! The process-wide Embassy time driver, advanced only by the executor.
//!
//! Embassy time equals simulation time. The executor validates that every
//! grant is monotonic before it is stored here.

use std::io;
use std::sync::Mutex;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::task::Waker;

use embassy_time_driver::Driver;
use embassy_time_queue_utils::Queue;

struct DiscreteTime {
    now: AtomicU64,
    queue: Mutex<Queue>,
}

embassy_time_driver::time_driver_impl!(static DRIVER: DiscreteTime = DiscreteTime {
    now: AtomicU64::new(0),
    queue: Mutex::new(Queue::new()),
});

impl Driver for DiscreteTime {
    fn now(&self) -> u64 {
        self.now.load(Ordering::Acquire)
    }

    fn schedule_wake(&self, at: u64, waker: &Waker) {
        let mut queue = self.queue.lock().unwrap();
        queue.schedule_wake(at, waker);
        queue.next_expiration(self.now());
    }
}

static ACTIVE: AtomicBool = AtomicBool::new(false);

/// Exclusive use of the driver by one executor, starting at time zero.
pub(crate) struct ClockLease(());

impl ClockLease {
    pub fn acquire() -> io::Result<Self> {
        ACTIVE
            .compare_exchange(false, true, Ordering::AcqRel, Ordering::Acquire)
            .map_err(|_| io::Error::other("only one discrete executor may be active per process"))?;
        *DRIVER.queue.lock().unwrap() = Queue::new();
        DRIVER.now.store(0, Ordering::Release);
        Ok(Self(()))
    }

    /// Publish a granted simulation time to Embassy.
    pub fn advance_to(&self, now_us: u64) {
        DRIVER.now.store(now_us, Ordering::Release);
    }

    /// Wake expired timers and return the earliest remaining deadline.
    pub fn next_deadline(&self) -> u64 {
        DRIVER.queue.lock().unwrap().next_expiration(DRIVER.now())
    }
}

impl Drop for ClockLease {
    fn drop(&mut self) {
        ACTIVE.store(false, Ordering::Release);
    }
}
