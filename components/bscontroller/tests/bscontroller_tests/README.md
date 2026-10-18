# RadioController Tests

The suites separate implementation invariants from Bluetooth protocol behavior. The [component README](../../README.md) documents installation, executable API examples, independent HCI service operation, and distribution builds.

| Directory | Responsibility | BabbleSim Requirement |
|---|---|---|
| `unit/` | Controller algorithms, state ownership, scheduler and FIFO/thread/clock boundaries, organized by implementation module. | No native PHY is required. |
| `qualification/` | All 501 selected HCI/LL cases, organized by their normative source chapters, with independent lower testers and explicit procedure registrations. | Required for RF cases; pure HCI checks run without it. |

The [qualification chapter map](qualification/README.md) defines the 17 primary test files. Each chapter registers its own case identifiers, descriptions, procedure arguments and pytest marks.

These independently implemented tests do not constitute Bluetooth qualification or imply complete LL.TS/HCI.TS coverage.

Native-PHY fixtures live in `qualification/conftest.py`. Controller unit fixtures and fake-radio helpers live in `unit/conftest.py` and `unit/helpers.py`. Independent packet encoders, raw peers, registration and protocol logging belong to `qualification/`. Protocol verdicts use independent wire observations rather than DUT implementations as their oracle. Unit tests serve the Controller implementation and do not test qualification code.

The [unit module map](unit/README.md) explains the retained boundaries: queue ownership, fragment state, counters, control instants, window admission, resource atomicity and failure cleanup. Independent fixed vectors protect codecs and algorithms; explicit boundary rows replace redundant parameter combinations. Public HCI results and on-air timing belong to the protocol suite. Samples exercise normal Host APIs and do not claim standard-case verdicts.

## Run

From the RadioController checkout:

```sh
# Self-contained implementation checks.
python -m pytest tests/bscontroller_tests/unit/ -v
```

For RF cases, select a BabbleSim build with the 2G4 v1/v2 FIFO protocols, `BLE_simple` modem and `multiatt` channel model:

```sh
export BSCONTROLLER_BSIM_DIR=/path/to/bsim
python -m pytest tests/bscontroller_tests/ -v -rs

# Full RadioController regression.
python -m pytest tests/ -v
```

Native cases have independent simulation IDs and support pytest-xdist. They skip when neither `BSCONTROLLER_BSIM_DIR` nor `BSIM_OUT_PATH` is set; a configured path without the PHY executable fails. Unit collection needs no native artifact.

## Parallel Execution

```sh
python -m pip install pytest-xdist
export BSCONTROLLER_BSIM_DIR=/path/to/bsim
python -m pytest tests/bscontroller_tests/ -n auto --dist worksteal -q -rs
```

Each native case owns its PHY process, simulation ID, FIFOs and packet dumps. Worker temporary directories and per-case protocol logs are also separate. Simulations do not interfere through equal RF channels or device addresses. If running multiple pytest invocations with explicit `--basetemp` values, give each invocation its own directory.

`--dist worksteal` redistributes pending cases when workers become idle. A single procedure is not split across workers. Use `-n 4` to choose a fixed worker count. Workers share CPU, memory and storage, so more workers do not guarantee a faster run.

## License

Copyright 2026 Xiaomi Corporation. The independently written tests are licensed under Apache License 2.0; see the repository [LICENSE](../../LICENSE).
