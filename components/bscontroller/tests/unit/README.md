# BSController unit tests

English | [简体中文](README.zh-CN.md)

The unit suite checks the Controller implementation in isolation. It needs no native PHY and does not evaluate protocol verdicts; HCI and on-air procedure results belong to [`../qualification/hci/`](../qualification) and `../qualification/ll/`.

The table below summarizes what the suite covers.

| Area | Invariants protected |
|---|---|
| `radio/base`, `linklayer/bitstream`, `linklayer/channel_selection`, `linklayer/parameters`, `linklayer/advertising` | Fixed wire/CRC/CSA vectors, strict input lengths, offset rounding, reproducible address allocation and switching boundaries. |
| `linklayer/discovery` | Scan gaps and overlapping PHY windows, backoff saturation/streaks and channel-map instants across counter wrap. |
| `linklayer/scheduler` | Half-open reservation endpoints, chained conflicts, complete nonpreemptive slots and request-relative scheduling grids. |
| `linklayer/link`, `linklayer/primary`, `linklayer/periodic` | One-radio arbitration, live identity collisions, starvation, missed anchors, acquisition/established lifetime transitions and callback-time context replacement. |
| `linklayer/extended` | Header-dependent capacity, PHY-aware chain spacing, identity inheritance and bounded/truncated reassembly. |
| `linklayer/connection`, `linklayer/control`, `linklayer/data_length` | Queue/ARQ ownership, empty Host fragments, exact credit return, delayed indications, retransmission snapshots, colliding negotiations and independent deadlines. |
| `linklayer/encryption` | Published cipher vectors, TX/RX nonce exhaustion, cached encrypted retries and refresh transitions that must keep user data blocked. |
| `hci/controller`, `hci/backend`, `hci/records`, `hci/le` | Decoder/backend isolation, shared handle publication, live public views and mutable advertising buffers across reconfiguration. |
| `hci/advertising`, `hci/scanning`, `hci/connection`, `hci/events` | Atomic failure/resource updates, fragment staging, per-context command routing and state completion when notifications are masked. |
| `radio/babblesim`, `runtime/session`, `runtime/event_loop`, `runtime/worker` | Fragmented FIFO I/O, wrong/late ACKs, clock admission, ready-work draining, worker-thread ownership and cleanup after cancellation or startup failure. |

## Run

```sh
python -m pytest tests/unit -n auto --dist worksteal -q
```
