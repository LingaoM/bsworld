// SPDX-License-Identifier: MIT OR Apache-2.0

//! Native H4 sockets and cooperative discrete-time execution.
//!
//! This module supplies the process-wide Embassy time driver. Application
//! futures run on one thread, without Tokio or an I/O worker.

pub mod babblesim;
mod executor;
mod time;
pub mod unix;

pub use executor::{Clock, Executor};

#[cfg(test)]
mod tests;
