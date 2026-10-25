// Copyright 2026 Xiaomi Corporation
// SPDX-License-Identifier: Apache-2.0

//! One TrouBLE Host joined to a BabbleSim simulation over an H4 Unix socket.
//!
//! The Host stack and the Battery Service applications come from the pinned
//! upstream commit; only the transport and executor are maintained by BSWorld.

mod bsim;

use std::io;
use std::path::Path;

use bsim::Executor;
use bsim::babblesim::BabbleSim;
use bt_hci::controller::ExternalController;
use trouble_example_apps::{ble_bas_central, ble_bas_peripheral};

/// HCI command/event queue depth for the external Controller.
const HCI_SLOTS: usize = 8;

fn main() -> io::Result<()> {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info"))
        // Simulation time is in the PHY trace; wall-clock stamps would only
        // make log comparisons across runs noisier.
        .format_timestamp(None)
        .init();

    let args: Vec<String> = std::env::args().collect();
    if args.len() != 6 || !matches!(args[1].as_str(), "central" | "peripheral") {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "usage: ble_bas central|peripheral SIM_DIR PHY_ID DEV_ID HCI_SOCKET",
        ));
    }
    let dev_id = args[4]
        .parse()
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "invalid device ID"))?;

    let clock = BabbleSim::connect(Path::new(&args[2]), &args[3], dev_id)?;
    let mut executor = Executor::new(clock)?;
    let controller = ExternalController::<_, HCI_SLOTS>::new(executor.connect_hci(&args[5])?);
    executor.block_on(async {
        if args[1] == "central" {
            ble_bas_central::run(controller).await;
        } else {
            ble_bas_peripheral::run(controller).await;
        }
    })
}
