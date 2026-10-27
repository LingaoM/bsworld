# Virtual Controllers

English | [简体中文](zh-CH/controllers.md)

Every Bluetooth Host in a BSWorld test talks to its own virtual Controller over standard H4 HCI on a Unix socket. The Controller runs the Link Layer and transmits through the shared BabbleSim PHY, so Controllers of different Hosts reach each other over the simulated radio.

BSWorld ships two implementations:

| | `ZephyrController` | `BSController` |
|---|---|---|
| Implementation | Zephyr Bluetooth Controller built for `nrf52_bsim` ([bt_virt_controller](../components/bt_virt_controller/README.md)) | Python Controller ([bscontroller](../components/bscontroller/README.md)) |
| Runs as | Native simulator process, one per Controller | Worker thread inside the pytest process |
| Needs | `BSWORLD_BT_VIRT_CONTROLLER_BIN` (prebuilt in the Docker image) | Nothing beyond the BSWorld installation |
| Configuration | Fixed by the Zephyr build | Per Controller: buffers, list sizes, limits, version ([below](#configuring-bscontroller)) |
| Default | Yes | Selected per test or per Controller |

Both write an HCI capture per Controller (`hciN.snoop`), and both appear in the shared radio trace (`ellisys.bttrp`). See [Logs, traces, and captures](artifacts.md).

## Adding Controllers to a test

`topo.add_controller()` returns a Controller. Connect a Host to its `hci_sock` after `topo.start()`:

```python
from bsworld.devices import BSController

zephyr_ctl = topo.add_controller(public_address="F0:F1:F2:F3:F4:02")
python_ctl = topo.add_controller(
    controller_type=BSController,
    public_address="F0:F1:F2:F3:F4:01",
)
await topo.start()
# Connect Hosts to zephyr_ctl.hci_sock and python_ctl.hci_sock.
```

| Argument | Meaning |
|---|---|
| `controller_type` | `ZephyrController` (default) or `BSController`. One topology may mix both. |
| `public_address` | Public device address, `AA:BB:CC:DD:EE:FF`. If omitted, `BSController` derives a distinct address from the Controller number, and `ZephyrController` keeps the address of its build. |
| `log_subdir` | Where this Controller's `hciN.snoop` goes, relative to the test log directory. |
| `config` | `BSController` only: a `ControllerConfig` with Controller-defined values, see [Configuring BSController](#configuring-bscontroller). |
| `max_step_us` | `BSController` only: longest simulation step the worker takes while idle. |

## Running a scenario against both Controllers

Override the `bsworld_default_controller_type` fixture to set the default `controller_type` of the `topo` fixture; an explicit `controller_type` still takes precedence:

```python
import pytest
from bsworld.devices import BSController, ZephyrController


@pytest.fixture(params=[ZephyrController, BSController], ids=["zephyr", "bscontroller"])
def bsworld_default_controller_type(request):
    return request.param
```

Select one implementation with its parameter ID:

```sh
pytest tests/integration -n auto -k '[zephyr]'
pytest tests/integration -n auto -k '[bscontroller]'
```

## Configuring BSController

Pass a `ControllerConfig` as `config=`. The fields, defaults and ranges are listed in the [BSController configuration reference](../components/bscontroller/README.md#configuration).

```python
from bscontroller import ControllerConfig
from bsworld.devices import BSController

central = topo.add_controller(
    controller_type=BSController,
    config=ControllerConfig(max_connections=1),
)
peripheral = topo.add_controller(
    controller_type=BSController,
    config=ControllerConfig(advertising_set_count=2, acl_packet_count=16),
)
```

## Using a Zephyr Controller

`ZephyrController` starts `$BSWORLD_BT_VIRT_CONTROLLER_BIN` once per Controller. The Docker image includes it; to build it, see the [bt_virt_controller guide](../components/bt_virt_controller/README.md). Its output is written to `bt_virt_controller/bt_virt_controller_hciN.log` in the test log directory.
