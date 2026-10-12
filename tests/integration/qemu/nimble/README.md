# QEMU NimBLE Linux Test

[English](README.md) | [中文](README.zh-CN.md)

This test runs the upstream Apache NimBLE Linux Host example inside the AArch64 Linux Guest. QEMU exposes the Virtual Controller's Unix-socket HCI stream as `/dev/ttyS0`, `btattach` registers the H4 serial transport as `hci0`, and the NimBLE Linux port claims that device through HCI User Channel. The integration neither modifies NimBLE source nor adds a BSWorld-specific transport.

## Validated Scenario

`test_qemu_nimble_linux_advertises_and_accepts_connection` validates the complete path:

1. NimBLE initializes its Host and Controller connection and starts connectable advertising.
2. An independent Bumble Central receives the advertisement over the simulated radio and verifies public address `AA:BB:CC:DD:EE:FE` and complete local name `nimble`.
3. Bumble connects to NimBLE, verifies a valid connection handle, and disconnects cleanly.

## Build and Run

First run the build entry point in the parent [QEMU Linux environment guide](../README.md). The BlueZ, NimBLE, and TrouBLE tests share the QEMU executable, Linux kernel, and Guest root filesystem under `tests/integration/qemu/prebuilt/`. Then run:

```sh
pytest tests/integration/qemu/nimble -q
```

Set `BSWORLD_QEMU_BIN`, `BSWORLD_QEMU_KERNEL`, or `BSWORLD_QEMU_ROOTFS` to use artifacts from another location.

The QEMU console is stored as `qemu/nimble/qemu_nimble.log`. HCI BTSnoop captures and BabbleSim RF traces are archived with the other per-test files described in [Logs, Traces, and Packet Captures](../../../../docs/artifacts.md).

## License

The tests in this directory are licensed under Apache License 2.0. Apache NimBLE is licensed under Apache License 2.0; QEMU, Linux, Buildroot, and other Guest packages retain their own licenses. Review [Third-Party Notices](../../../../THIRD_PARTY_NOTICES.md) and the parent guide's [packaging requirements](../README.md#packaging-and-license-compliance) before distributing binaries.
