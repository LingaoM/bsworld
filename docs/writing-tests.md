# Writing Tests

[English](writing-tests.md) | [中文](zh-CH/writing-tests.md)

The repository [README](../README.md#technical-architecture) introduces the Virtual Controller and discrete-time scheduler. This guide follows the practical test-authoring workflow: declare a topology, integrate Applications, drive and await behavior with asyncio, configure RF conditions, and verify the expected Bluetooth LE result.

## Quick Index

- [Test Lifecycle](#test-lifecycle)
- [Choosing Controllers](#choosing-controllers)
- [Async Waiting and Simulation Time](#async-waiting-and-simulation-time)
- [Integrating Application Processes](#integrating-application-processes)
- [Process Shell Commands](#process-shell-commands)
- [RF Conditions and Interference](#rf-conditions-and-interference)
- [Topology as a pytest Test](#topology-as-a-pytest-test)

## Test Lifecycle

The `topo` fixture gives each test a `BluetoothTopology`. Tests declare participants, connectivity, and RF conditions instead of orchestrating operating-system processes directly. Suite-local adapters register native Applications as `ProcessInstance` objects with log waiting and optional shell input; asyncio-based Python Host stacks register Virtual Controllers directly and open their HCI sockets after topology startup.

The topology moves through four phases:

1. Suite-local process loaders, `topo.add_controller()`, and RF configuration methods record the intended topology without spawning processes or advancing simulation time.
2. `await topo.start()` assigns Controller, Application, and PHY device identities; prepares isolated socket and log paths; and starts the PHY, Virtual Controllers, interference sources, and Application processes. It then connects pytest's clock client to the PHY. Once the HCI sockets are ready and all participants have registered, a WAIT/ACK exchange at simulation time zero ensures they have submitted their initial requests. Only then does `start()` bind the simulation clock to the event loop and return.
3. Tests drive behavior and evaluate results through `ProcessInstance`, in-process Host stack APIs, shell commands, and standard asyncio APIs. The event loop advances shared simulation time only after all callbacks and I/O at the current timestamp have been processed.
4. Fixture teardown unbinds the simulation clock from the event loop, stops Controllers and processes, closes capture files, and flushes logs. The BabbleSim backend then closes its FIFO clock connection, generates the Ellisys trace, and removes temporary simulation files.

Every test receives its own simulation ID, Unix socket directory, and log directory. Virtual tests can therefore run concurrently without sharing Controller state, RF state, or output files.

## Choosing Controllers

Each Host can use either `ZephyrController` (the default native process) or `BSController` (a Python Controller running in its own worker thread). Both expose the same H:4 Unix socket. Controller choice is independent of whether the Host runs in Python or an external process.

Install the Python implementation locally with `python -m pip install -e components/bscontroller`; the Docker test image includes it.

```python
from bsworld.devices import BSController

python_ctl = topo.add_controller(
    controller_type=BSController,
    public_address="F0:F1:F2:F3:F4:01",
)
zephyr_ctl = topo.add_controller(
    public_address="F0:F1:F2:F3:F4:02",
)
await topo.start()
# Connect Hosts to python_ctl.hci_sock and zephyr_ctl.hci_sock.
```

Each Python Controller owns its worker, radio endpoint and address. Omit `max_step_us` to use bscontroller's default; pass it only to override the worker's step size. Both implementations use the shared PHY and framework clock. A topology containing only Python Controllers does not require `BSWORLD_BT_VIRT_CONTROLLER_BIN`.

New implementations subclass `Controller` and implement asynchronous `start(pm, env, *, log_dir)` and `stop()`. The base class provides the HCI socket path and device metadata. Startup launches the runtime without waiting for other PHY participants; returning does not guarantee that the HCI socket is ready. The backend waits for socket readiness, and the topology completes registration after launching the Hosts. Shutdown releases resources even after a partial startup failure.

## Async Waiting and Simulation Time

BSWorld preserves the standard asyncio programming model. Tests do not need simulation-specific task, I/O, sleep, or timeout APIs. Pytest runs on a `BsimEventLoop`, which retains asyncio's tasks, futures, queues, events, streams, and sockets; only its source of time and blocking behavior change after simulation startup.

The event loop initially follows wall-clock time while the test prepares its topology. Once `await topo.start()` has launched and registered every BabbleSim participant, BSWorld binds the BabbleSim clock client to the loop. From that point, `loop.time()` advances with simulation time, and APIs such as `asyncio.sleep()` and `asyncio.wait_for()` use the same clock. A `timeout=30` therefore allows 30 simulated seconds, not 30 seconds of wall-clock time:

```python
import asyncio

await topo.start()

await dev.wait_log("ready", timeout=30)
await asyncio.sleep(0.2)
result = await asyncio.wait_for(operation(), timeout=5)
```

BSWorld implements this transition without replacing asyncio's task scheduler or I/O machinery. It intercepts only the selector wait reached when no work is immediately ready. A normal event loop would block there in wall-clock time; `BsimEventLoop` instead calculates the next target and advances BabbleSim through its FIFO protocol. Each cycle follows four stages:

1. Poll registered file descriptors without blocking, then run callbacks and I/O that are ready at the current timestamp.
2. When no work remains, compute a target from the next timer deadline and the maximum step size, then send a WAIT request.
3. The pytest clock waits on its BabbleSim response FIFO until the PHY acknowledges the requested target.
4. The event loop processes the resulting socket events and expired timers under normal asyncio semantics. It does not advance time again until all work at the current timestamp is complete.

Figure 1 follows one complete advancement: the selector calls the in-process BabbleSim clock client, which sends a WAIT request over its FIFO. Once the PHY acknowledges the target, pytest handles the resulting I/O and timers.

<div align="center"><img src="images/bluetooth-diagram.svg" alt="One BSWorld discrete-time step" width="80%"><br><em>Figure 1: One deterministic simulation-time step</em><br><br></div>

`ProcessInstance.wait_log()` uses the same asynchronous clock, so its `timeout` is also measured in simulation time. It applies a regular expression to complete buffered and newly arriving lines in arrival order. A fragment is not eligible until its terminating newline arrives, and a later call does not revisit lines that have already been scanned. Write consecutive log assertions in the expected event order.

> [!WARNING]
> Do not call blocking functions such as `time.sleep()` inside an async test because they block the event loop thread. Prefer asynchronous APIs; host-side blocking work that does not participate in protocol timing can be moved to `asyncio.to_thread()` when unavoidable.

## Integrating Application Processes

BSWorld core provides generic Virtual Controller, `ProcessInstance`, and topology lifecycle primitives without embedding platform argument formats. Each integration suite owns the profile and loader that translate its launch contract into a BSWorld topology. Zephyr, NuttX, and future platform differences therefore remain outside the framework core.

### NuttX

`NuttXProcessProfile` defines the Application environment variable, Controller address, and optional shell support. `load_nuttx_profile()` adds the `--sim-bsim-*` device identity and the HCI socket as `--bt-dev=<sock>`:

```python
from tests.integration.nuttx.common import NuttXProcessProfile, load_nuttx_profile

MY_DEVICE = NuttXProcessProfile(
    name="my_device",
    binary_env="BSWORLD_NUTTX_BTSAK_BIN",
    controller_address="C0:FF:EE:00:00:01",
)
```

The generated command has this form:

```text
my_device --sim-bsim-sid=<sim_id> --sim-bsim-pid=2G4 \
  --sim-bsim-dev=<dev_id> --bt-dev=<sock>
```

### Zephyr

A Host-only Zephyr Application uses native simulator-style device identity arguments:

```python
from tests.integration.zephyr.samples.common import ZephyrProcessProfile, load_zephyr_profile

ZEPHYR_APP = ZephyrProcessProfile(
    name="zephyr_app",
    binary_env="BSWORLD_ZEPHYR_OBSERVER_BIN",
    controller_address="C0:FF:EE:10:00:01",
)
```

`load_zephyr_profile()` generates `-s=<sim_id> -p=<phy_id> -d=<dev_id> -mro=1000` and uses `--bt-dev=<sock>` to connect Zephyr `userchan` to the external Virtual Controller.

Both loaders allocate a Virtual Controller, register a `ProcessInstance`, and defer command construction until `topo.start()` has assigned final device identities and socket paths. `controller_address` belongs to that Controller. The Virtual Controller receives `-bd-addr=<addr>` and initializes its public BD_ADDR before the Host establishes the HCI connection.

### Python Host Stacks

Python Host stacks do not need a `ProcessInstance`. Bumble tests call `topo.add_controller()`, start the topology, and open the returned Controller's `hci_sock` through a Unix transport. Because Bumble runs in pytest's asyncio event loop, its tasks, I/O, and timeouts automatically use the same simulation clock. See the [Bumble integration tests](../tests/integration/bumble/README.md) for the complete setup.

## Process Shell Commands

Some firmware images expose a shell on standard input. Enable `shell=True` and send commands from the test after `await topo.start()`, which establishes the initial PHY synchronization boundary:

```python
from tests.integration.nuttx.common import NuttXProcessProfile, load_nuttx_profile

NUTTX_APP = NuttXProcessProfile(
    name="nuttx_app",
    binary_env="BSWORLD_NUTTX_NIMBLE_BIN",
    shell=True,
)


async def test_staged(topo):
    dev = load_nuttx_profile(topo, NUTTX_APP)
    await topo.start()

    await dev.shell.run("ifup bnep0")
    await dev.shell.run("bleprph")
```

`await dev.shell.run()` writes one command line to standard input; it does not wait for command completion. Follow it with `wait_log()` or another observable condition when the result matters. The abstraction can drive a Zephyr shell, NuttX NSH, or any process console that accepts line-oriented commands on standard input.

## RF Conditions and Interference

Configure RF conditions before `await topo.start()`; the PHY configuration and participant set are immutable after startup. Attenuation and interference sources share one BabbleSim PHY with all Virtual Controllers. The PHY uses the `BLE_simple` modem by default, so RSSI, SNR, and path attenuation affect packet reception.

### Channel Attenuation

```python
topo.set_channel_attenuation(
    default_db=70.0,
    extra_db=0.0,
)
```

| Parameter | Default | Meaning |
|---|---|---|
| `default_db` | `60.0` | Path loss for every directed `tx -> rx` path not covered by a static or timed override. |
| `extra_db` | `0.0` | Extra attenuation added on top of every path. |
| `matrix_file` | `None` | Path to a raw `multiatt` matrix file. Mutually exclusive with generated paths. |
| `static_paths` | `[]` | List of fixed per-path attenuation values. |
| `timed_paths` | `[]` | List of time-varying per-path attenuation curves. |

### Per-Path Attenuation

```python
from bsworld.interference import StaticAttenuation, TimedAttenuation
from tests.integration.zephyr.samples.common import load_zephyr_profile
from tests.integration.zephyr.samples.heart_rate.devices import ZEPHYR_CENTRAL_HR, ZEPHYR_PERIPHERAL_HR

peripheral = load_zephyr_profile(topo, ZEPHYR_PERIPHERAL_HR)
central = load_zephyr_profile(topo, ZEPHYR_CENTRAL_HR)

topo.set_channel_attenuation(
    default_db=50.0,
    static_paths=[
        StaticAttenuation(
            tx=peripheral,
            rx=central,
            attenuation_db=55.0,
        ),
    ],
    timed_paths=[
        TimedAttenuation(
            tx=central,
            rx=peripheral,
            times_us=[0, 10_000_000, 20_000_000],
            attenuation_db=[50.0, 80.0, 50.0],
        ),
    ],
)
```

Paths are directional. Configure both `tx -> rx` and `rx -> tx` when the two directions require distinct loss values. A `TimedAttenuation` curve pairs each timestamp with one attenuation value and linearly interpolates between adjacent points.

`tx` and `rx` can be registered `ProcessInstance` or `Controller` objects, `InterferenceRef` objects returned by `add_*_interference()`, or raw BabbleSim device IDs. An Application process resolves to its associated Virtual Controller because the Controller is the RF participant that exchanges packets with the PHY.

### Burst Interference

```python
jammer = topo.add_burst_interference(
    center_freq_mhz=2402.0,
    power_dbm=10.0,
    interf_type="CW",
    windows=[],
    rand_seed=None,
)
```

`windows=[]` keeps the source active for the full simulation; use `[(start_us, end_us)]` for bounded windows. The returned `InterferenceRef` can be used as the `tx` endpoint of `StaticAttenuation` or `TimedAttenuation` to control loss from the source to a particular receiver.

### WLAN Activity Model

```python
topo.add_wlan_interference(
    channel=6,
    power_dbm=20.0,
    config_set="VideoConf",
)
```

Specify the frequency with exactly one of `channel=1..14` and `center_freq_mhz=<MHz>`. `config_set` selects a traffic profile such as `VoIP`, `VideoConf`, `FileDownload`, `100`, `50`, `25`, `10`, or `5`.

### Playback Interference

```python
topo.add_playback_interference("path/to/recording")
```

The input path is a prefix. BabbleSim expects `.Tx.csv`, `.Rx.csv`, `.RSSI.csv`, and `.CCA.csv` files with that prefix.

### Parameter Constraints

BSWorld validates RF inputs before spawning BabbleSim processes:

| Area | Parameter | Accepted range |
|---|---|---|
| Burst / WLAN | `center_freq_mhz` | `> 2273.0` and `< 2527.0` MHz. The API expects absolute MHz; common Bluetooth LE advertising channels are 2402, 2426, and 2480 MHz. |
| Burst / WLAN | `power_dbm` | `-128.0 .. 127.0` dBm. |
| Burst / WLAN | `windows` | At most 256 windows. Each `(start_us, end_us)` must use integer microseconds, `start_us > 0`, `end_us > start_us`, and windows must be strictly ordered and non-overlapping. `[]` enables the source for the full run. |
| Burst / WLAN | `rand_seed` | Unsigned 32-bit integer, `0 .. 4294967295`. |
| Burst / WLAN | `interf_type` / `mod_type` | `"CW"`, `"WLAN"`, `"BLE"`, `"WN1"`, `"WN2"`, `"WN4"`, `"WN8"`, `"WN16"`, `"WN20"`, `"WN40"`, `"WN80"`. |
| WLAN | `channel` | Wi-Fi channel `1 .. 14`; channel 14 maps to 2484 MHz. |
| WLAN | `config_set` | `"VoIP"`, `"VideoConf"`, `"FileDownload"`, `"FileDownload_24M"`, `"FileDownload_12M"`, `"FileDownload_6M"`, `"100"`, `"100_24M"`, `"100_12M"`, `"100_6M"`, `"50"`, `"50_24M"`, `"50_12M"`, `"50_6M"`, `"25"`, `"25_24M"`, `"25_12M"`, `"25_6M"`, `"10"`, `"10_24M"`, `"10_12M"`, `"10_6M"`, `"5"`. |
| Channel | `default_db` / `extra_db` | `-100.0 .. 100.0` dB. |
| Channel | `StaticAttenuation.attenuation_db` | Any finite dB value. The value is written to the matrix file for the selected path. |
| Channel | `TimedAttenuation.times_us` | Integer microseconds, `>= 0`, strictly ascending, with at least two points. |
| Channel | `TimedAttenuation.attenuation_db` | A sequence of finite dB values with the same length as `times_us`; adjacent points are linearly interpolated. |

## Topology as a pytest Test

The `topo` fixture keeps topology declarations, RF conditions, Application actions, and assertions in one Python test. Process loaders and RF configuration calls record the desired state; `await topo.start()` materializes it as a running simulation.

```python
from tests.integration.zephyr.samples.common import load_zephyr_profile
from tests.integration.zephyr.samples.heart_rate.devices import ZEPHYR_CENTRAL_HR, ZEPHYR_PERIPHERAL_HR


async def test_central_receives_notification(topo):
    peripheral = load_zephyr_profile(topo, ZEPHYR_PERIPHERAL_HR)
    central = load_zephyr_profile(topo, ZEPHYR_CENTRAL_HR)
    topo.set_channel_attenuation(default_db=45.0)

    await topo.start()

    await peripheral.wait_log(r"Advertising successfully started")
    await central.wait_log(r"Connected")
    await central.wait_log(r"\[NOTIFICATION\]")
```

Figure 2 maps the example to its runtime behavior. Process loaders register each Application and its Controller, while `set_channel_attenuation()` configures RF paths on their shared PHY. Phase 1 corresponds to `topo.start()`, which returns only after the HCI sockets and all BabbleSim participants are ready. The remaining phases correspond to the three `wait_log()` calls as the event loop advances simulation time through advertising, connection establishment, and notification delivery.

<div align="center"><img src="images/pytest-topology-execution.svg" alt="A pytest topology expanded into deterministic Bluetooth LE execution" width="80%"><br><em>Figure 2: From a pytest topology to deterministic Bluetooth LE execution</em><br><br></div>

The lower half of the figure relates each log assertion to its HCI commands, events, and simulated over-the-air packets. The test states observable outcomes; BSWorld owns device and socket allocation, process lifecycles, time advancement, and persistence of logs and protocol traces.
