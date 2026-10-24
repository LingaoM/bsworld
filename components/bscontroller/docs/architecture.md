# BSController architecture

English | [简体中文](architecture.zh-CN.md)

This page describes how BSController is layered and how data flows through it, to support integration and debugging. The protocol behavior follows Bluetooth Core 6.3; the supported feature set is listed in the [component README](../README.md).

## Layers

BSController presents a standard HCI boundary to the Host and a BabbleSim PHY boundary to the radio medium. Between them it runs three protocol layers plus a runtime that drives the simulation clock.

```text
Host  ──H4 HCI bytes──►  HCI  ──►  Link Layer  ──►  Radio  ──FIFO──►  BabbleSim PHY
      ◄──H4 HCI bytes──       ◄──          ◄──             ◄──FIFO──
```

| Layer | Boundary it owns | What it does |
|---|---|---|
| **HCI** | H4 transport to the Host | Frames and validates HCI commands, rejects unsupported commands before decoding, translates wire units into Link Layer values, and encodes Link Layer notifications as HCI events (applying event masks, duplicate filtering, and report fragmentation). |
| **Link Layer** | Internal protocol state | Owns advertising, scanning, initiation, periodic synchronization, ACL connection state, LL control procedures, encryption, channel selection, and radio-slot scheduling. |
| **Radio** | FIFO to the PHY | Exposes transmit, receive, and physical-time services, and adapts them to the BabbleSim FIFO protocol and RF parameters. |
| **Runtime** | Threads, clock, process | Composes the worker thread, the simulation-time event loop, the session lifecycle, and the BabbleSim PHY process. |

Layering is one-directional: the Link Layer does not depend on HCI. Shared primitives (device address, Controller error codes, serialization helpers) sit below both layers, and HCI re-exports the shared protocol types used for packet construction.

## Command and event flow

A Host command and its response cross every layer:

1. The Host writes an H4 HCI command to the Unix socket (or calls `on_packet` in process).
2. HCI frames the packet, filters unsupported commands, and validates parameters. Invalid or unsupported commands return a Command Complete or Command Status with a Controller error code without reaching the Link Layer.
3. For accepted commands, HCI converts wire units (for example, 10 ms supervision fields to internal microseconds) and invokes the matching Link Layer operation.
4. The Link Layer updates protocol state and schedules radio work.
5. Link Layer notifications flow back to HCI, which applies event masks and duplicate filtering, fragments advertising reports, and emits HCI events to the Host.

## Radio and simulation time

The Link Layer requests transmit and receive slots from its scheduler, which enforces non-overlapping, non-preemptive reservations. The Radio layer renders those slots as BabbleSim FIFO requests and receives results, data, and timestamps back from the PHY.

All RF time is integer microseconds. Each worker holds its own clock endpoint and synchronizes with the shared simulation timeline through the PHY; a standalone Host clock, when used, needs a PHY device identity distinct from every Controller. Timing such as window widening, guard intervals, and the LE inter-frame space is defined in simulation time, so host load changes execution duration but not the protocol timeline. For thread, clock, and resource ownership see the [component README](../README.md#threads-clocks-and-resource-ownership).

## Implementation limits

The following are intentionally not implemented and affect what a Host or test can expect:

- No privacy address generation, SMP pairing protocol, or key database. Only AES `e` is provided, for HCI Encrypt and LL session-key derivation.
- No L2CAP reassembly, BR/EDR/LMP execution, or GAP advertising-data interpretation. HCI/LL process raw payloads; the Host owns higher-layer assembly.
- No LocalLink fallback or direct Controller-to-Controller delivery. All Controllers interact through the shared PHY.
- Resource capacities and supported PHY masks are this implementation's capabilities, not normative Bluetooth maxima.

## Specification references

- [Vol 1, Part A, 2: Core system architecture](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core_v6.3/out/en/architecture,-change-history,-and-conventions/architecture.html) — Host, Controller, resource manager, Link Controller, and PHY responsibilities.
- [Vol 1, Part F: Controller Error Codes](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core_v6.3/out/en/architecture,-change-history,-and-conventions/controller-error-codes.html).
- [Vol 4, Part E: HCI functional specification](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core_v6.3/out/en/host-controller-interface/host-controller-interface-functional-specification.html).
- [Vol 6, Part A: Radio Physical Layer](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core_v6.3/out/en/low-energy-controller/radio-physical-layer-specification.html).
- [Vol 6, Part B: Link Layer](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core_v6.3/out/en/low-energy-controller/link-layer-specification.html).
- [Vol 6, Part E: Low Energy Link Layer Security](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core_v6.3/out/en/low-energy-controller/low-energy-link-layer-security.html).
