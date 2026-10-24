# RadioController Protocol Tests

English | [简体中文](PROTOCOL.zh-CN.md)

The suite is organized by the actual HCI and LL test-suite chapters. These tests do not imply Bluetooth SIG qualification or certification.

## Chapter Layout

The suite contains 17 primary test files: nine HCI chapters and eight LL chapters. Each source procedure has one test method; its case variants are parameters of that method. A printed page label is not a section number.

| Directory | Source Chapter | Test File | Selected Cases |
|---|---|---|---:|
| `hci/` | 4.3 Generic Events | `generic_events_test.py` | 5 |
| `hci/` | 4.4 Device Setup | `device_setup_test.py` | 5 |
| `hci/` | 4.5 Controller Flow Control | `controller_flow_control_test.py` | 1 |
| `hci/` | 4.6 Controller Information | `controller_information_test.py` | 5 |
| `hci/` | 4.7 Device Discovery | `device_discovery_test.py` | 68 |
| `hci/` | 4.8 Host Flow Control | `host_flow_control_test.py` | 1 |
| `hci/` | 4.10 Controller Configuration | `controller_configuration_test.py` | 13 |
| `hci/` | 4.13 LE Connection Management | `connection_management_test.py` | 6 |
| `hci/` | 4.17 Event Versioning | `event_versioning_test.py` | 5 |
| `ll/` | 4.2 Device Discovery | `device_discovery_test.py` | 113 |
| `ll/` | 4.3 Connection | `connection_test.py` | 197 |
| `ll/` | 4.4 Timing | `timing_test.py` | 21 |
| `ll/` | 4.5 Encoding | `encoding_test.py` | 7 |
| `ll/` | 4.6 Frequency Hopping | `frequency_hopping_test.py` | 6 |
| `ll/` | 4.7 Packet Handling | `packet_handling_test.py` | 6 |
| `ll/` | 4.8 Security | `security_test.py` | 38 |
| `ll/` | 4.9 Data Flow | `data_flow_test.py` | 4 |

The chapter counts total 109 HCI and 392 LL cases, 501 selected cases in all. Additional regression cases do not increase coverage of these selected cases.

## Result Meaning

An unlabelled procedure that completes its assertions produces a protocol `PASS`. Two independent pytest markers describe execution limits and map to a `PARTIAL` verdict:

- `limited` is reserved for sub-microsecond stimulus or measurement precision. These cases execute all available checks at 1-us resolution, using documented integer-us approximations. Timing precision alone never permits a skip; the executor rejects skips from timing-only limited procedures.
- `source_conflict` identifies an unresolved source procedure, branch, or verdict requirement. It permits skipping the unresolved source path and does not imply a Controller capability gap.

A case may carry both markers; a mixed case can skip for its independent source question. A successful labelled execution produces a pytest pass and a protocol `PARTIAL` verdict, preserving the precision or source qualification boundary. An approximate execution is never represented as an exact fractional-time measurement.

A case without an executable procedure has an explicit pytest skip reason. `not_applicable` is distinct from `unsupported`: the former means the case's applicability conditions are false for this Controller. For example, `HCI/DDI/BI-03-C` requires a Controller without LE Set Periodic Advertising Receive Enable support, which this Controller provides, so the case is not applicable.

These independently implemented tests do not imply complete LL.TS/HCI.TS coverage.

## Run

```sh
export BSIM_OUT_PATH=/path/to/bsim/build
python -m pytest tests/qualification -n auto --dist worksteal -v -rs

# Protocol tests and implementation unit tests.
python -m pytest tests/ -n auto --dist worksteal -v -rs

# Precision-only cases must execute when the native PHY is available.
python -m pytest tests/qualification -m 'limited and not source_conflict' -v

# Includes source-only and mixed cases; unresolved source paths may skip.
python -m pytest tests/qualification -m source_conflict -v -rs
```

## Limits

`BSIM_SCAN_MAX_CODED_RANGE_M` declares the simulated `TSPX_scan_max_coded_range` in meters for the Coded latest-scanner case. Its default is 0 for colocated simulated endpoints. The stimulus applies the source's half-us range-delay floor before rounding the combined response delay to whole microseconds, and records the declaration in the protocol log.

Parallel cases have independent PHY processes, simulation IDs, FIFOs and log directories, so identical channels in different simulations cannot interfere. Workers share host resources; some source procedures remain long because they require repeated complete packet observations or simulated silence windows. Parallel scheduling leaves each case's steps, simulation timing and verdict requirements unchanged. See [parallel execution](../README.md#parallel-execution) for installation and worker selection.

## License

Copyright 2026 Xiaomi Corporation. Licensed under Apache License 2.0; see [LICENSE](../../LICENSE).
