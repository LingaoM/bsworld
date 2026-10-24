# BSController

English | [简体中文](README.zh-CN.md)

BSController is a Python Bluetooth LE Controller that can be installed, run, and published independently. Its import package and command-line entry point are both named `bscontroller`. It exposes an H4 HCI byte interface to the Host, executes LE link-layer procedures, and uses a BabbleSim PHY for radio transmission, reception, and discrete-time synchronization.

Supported features include legacy advertising, active and passive scanning, extended advertising, periodic advertising and synchronization, ACL connections, link-layer encryption, data-length negotiation, channel selection, and PHY updates across LE 1M, LE 2M, and LE Coded PHYs. Privacy, ISO, PAwR, and Bluetooth Classic are not implemented.

## Installation and execution

The module requires Python 3.11 or newer and [BabbleSim](https://babblesim.github.io/) for RF simulation, running on Linux. The following instructions use Ubuntu 24.04 x86_64. Install the build tools first:

```sh
sudo apt-get update
sudo apt-get install -y git repo build-essential gcc-multilib g++-multilib python3-venv
```

Follow the [official BabbleSim fetching instructions](https://babblesim.github.io/fetching.html) to download the sources, then build the PHY, modem, and channel needed by this module:

```sh
mkdir -p "$HOME/bsim"
cd "$HOME/bsim"
repo init -u https://github.com/BabbleSim/manifest.git -m everything.xml -b master
repo sync

export BSIM_OUT_PATH="$PWD/build"
export BSIM_COMPONENTS_PATH="$PWD/components"

make -j"$(nproc)" ext_2G4_phy_v1 ext_2G4_modem_BLE_simple ext_2G4_channel_multiatt
```

Build outputs are placed in `$BSIM_OUT_PATH/bin/` and `$BSIM_OUT_PATH/lib/`. Retain these exports when running BSController; the CLI, examples, and RF tests use `BSIM_OUT_PATH` directly. See the [official BabbleSim build instructions](https://babblesim.github.io/building.html) for more options.

After building BabbleSim, return to this module's source root and install the Python package:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
bscontroller --help
```

## Technical architecture

Each Controller implements HCI, the Link Layer, and radio adaptation. Multiple Controllers connect to the same BabbleSim PHY and interact through shared radio channels on a common simulation timeline.

<div align="center"><img src="docs/images/radio_controller_arch.svg" alt="Multiple Radio Controllers sharing a BabbleSim PHY" width="100%"><br><em>Figure 1: Controller protocol architecture and shared PHY</em></div>

The protocol behavior follows Bluetooth Core 6.3. See the [architecture overview](docs/architecture.md) for the layering, command and event flow, and implementation limits relevant to integration and debugging.

## Running examples

[examples/advertise_scan.py](examples/advertise_scan.py) exposes a scanning Controller through a standard H4 HCI Unix socket and implements a Mock Host that only exchanges HCI bytes over that socket. A second Controller transmits advertisements through the shared PHY, providing simulated RF input.

```sh
python examples/advertise_scan.py
```

```mermaid
sequenceDiagram
    participant Host as Mock Host
    participant H4 as H4 Unix socket
    participant Scan as Scanning Controller
    participant PHY as BabbleSim PHY
    participant Adv as Advertising Controller
    Note over Scan,Adv: Two Controllers and one Host clock endpoint join the shared PHY
    Note over Adv: The example configures and enables advertising through HCI first
    Host->>H4: HCI Reset / Set Event Mask / LE Set Event Mask
    H4->>Scan: H4 command bytes
    Scan-->>H4: Command Complete
    H4-->>Host: H4 event bytes
    Host->>H4: LE Set Scan Parameters / LE Set Scan Enable
    H4->>Scan: H4 scanning commands
    Scan-->>H4: Command Complete
    H4-->>Host: H4 event bytes
    Scan->>PHY: RX: scan channel and receive window
    Adv->>PHY: TX: advertising PDU
    PHY-->>Scan: Receive result, data, and timestamps
    Scan-->>H4: LE Advertising Report
    H4-->>Host: H4 event bytes
    Note over Host: Validate advertiser address and payload
    Host->>H4: LE Set Scan Enable = 0
    H4->>Scan: Stop scanning
    Scan-->>H4: Command Complete
    H4-->>Host: H4 event bytes
```

The example exercises the Host's H4 transport boundary, HCI command processing, and PHY advertising reception path. See [examples/README.md](examples/README.md) for details.

Expose H4 HCI to an external Host:

```sh
bscontroller serve --hci-socket /tmp/radio.sock --btsnoop-file /tmp/hci.snoop
```

Use `hci_snoop_file=Path(...)` when constructing `RadioController`, or `--btsnoop-file` with the CLI, to write a BTSnoop v1 H4 capture. The worker records complete HCI packets with its local simulation timestamps before handing output to the Host loop. Records are written without user-space buffering; capture does not advance simulation time. BSWorld supplies this path automatically.

The Host exchanges an H4 HCI byte stream over the Unix socket. The service accepts one Host and exits when it disconnects; the socket path must be unused. See `bscontroller serve --help` for more options.

## Threads, clocks, and resource ownership

Create `RadioController` inside the Host's running event loop; it runs its Controller in a dedicated thread. The Host and the worker never share mutable protocol state, so Host input and Controller output are passed as immutable H4 packets.

RF time uses integer microseconds. Each worker keeps its own clock endpoint and synchronizes with the shared simulation timeline through the PHY. A standalone Host may use an additional clock endpoint, which needs a PHY device identity distinct from every Controller.

| Object | Resources it manages |
| --- | --- |
| `RadioController` | One worker thread, Controller event loop, and radio FIFO endpoint |
| `RadioSession` | Worker startup and shutdown, plus an optional standalone Host clock connection and loop binding |
| `H4Server` | Unix socket, one Host connection, H4 framing, and a bounded output queue |
| `PhyProcess` | BabbleSim PHY subprocess, logs, and simulation directory cleanup |

`RadioSession` connects to an already running PHY; it does not start that process. With `clock_dev_id`, the Host must use `RadioEventLoop`. Without it, the caller supplies a synchronized clock and event loop and owns device identities, startup barriers, and time binding. Stop workers before closing the Host clock and PHY. The CLI and example already combine these lifecycles.

## Python integration

Public exports include `RadioController`, `RadioSession`, `RadioEventLoop`, `Radio`, `Phy`, `Received`, and `hci`. For a direct connection, send complete H4 packets with `controller.on_packet(packet)` and register an output sink with `controller.set_packet_sink(sink)` before starting the worker. The sink must implement `on_packet(packet: bytes)`.

For an external Host, pass `hci_socket` to `RadioController`. The worker owns socket reads, H4 parsing, and replies in its Controller thread. Startup returns once the socket is listening; commands wait until the worker has received its initial PHY grant at time zero and bound its clock. Socket mode does not use the cross-thread packet queue or HCI polling timer.

This example joins a PHY already started by the caller. The PHY must use the same `sim_id` and have two devices: identity `0` for the Controller and `1` for the Host clock.

```python
import asyncio
from pathlib import Path

from bscontroller import RadioController, RadioEventLoop, RadioSession


async def main():
    controller = RadioController(
        "controller", "F0:F1:F2:F3:F4:01", hci_socket=Path("/tmp/radio.sock")
    )
    async with RadioSession("example", [(0, controller)], clock_dev_id=1):
        await controller.terminated


with asyncio.Runner(loop_factory=RadioEventLoop) as runner:
    runner.run(main())
```

## Layout and verification

```text
.
├── pyproject.toml
├── src/bscontroller/     # Runtime package (public API, HCI, Link Layer, radio, runtime)
├── examples/             # Runnable H4 Controller and Mock Host example
└── tests/
    ├── unit/             # Self-contained implementation checks (no native PHY)
    └── qualification/    # HCI/LL protocol cases (RF cases need BabbleSim)
```

```sh
python -m pip install -e '.[test]'
python -m pytest tests/unit -n auto --dist worksteal -q
python -m pytest tests/qualification -n auto --dist worksteal -v -rs
python -m build
```

The protocol suite contains 501 selected HCI/LL cases, retaining distinct `PASS`, `PARTIAL`, source-conflict skips, and applicability skips. Timing-limited cases use their documented integer-microsecond approximation. These results are not a Bluetooth qualification claim. See [tests/README.md](tests/README.md) for test scope and execution details.

Build artifacts are written to `dist/`. The source distribution includes the runtime, examples, and unit and protocol tests; the wheel contains the runtime and required license notices. See [LICENSE](LICENSE) and [NOTICE](NOTICE) for licensing and third-party attribution.
