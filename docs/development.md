# Development Checks

[English](development.md) | [简体中文](zh-CH/development.md)

Run BSWorld's unit tests, lint checks, and coverage from the repository root. The [published Docker image](../docker/README.md#run-tests) is the shortest setup; use the README's [local Linux setup](../README.md#local-linux) when you need a native Python environment.

## Unit Tests

With Docker:

```sh
sudo docker run --rm \
  --mount "type=bind,src=$PWD,dst=/workspace,readonly" \
  --env PYTHONDONTWRITEBYTECODE=1 \
  -e PYTHONPATH=/workspace \
  ghcr.io/xiaomi/bsworld:latest pytest tests/unit -q -p no:cacheprovider
```

With the local virtual environment:

```sh
cd "$BSWORLD_ROOT"
source .venv/bin/activate
pytest tests/unit -q
```

The unit suite covers environment and artifact resolution, topology and Controller lifecycle, BabbleSim command generation, RF configuration, simulation-time scheduling, FIFO clock communication, and log collection. End-to-end Bluetooth behavior is covered by `tests/integration/`.

## Lint

With Docker:

```sh
sudo docker run --rm \
  --mount "type=bind,src=$PWD,dst=/workspace,readonly" \
  -e PYTHONPATH=/workspace \
  ghcr.io/xiaomi/bsworld:latest ruff check --no-cache src tests
```

With the local virtual environment:

```sh
ruff check src tests
```

To apply safe automatic fixes locally:

```sh
ruff check --fix src tests
```

## Coverage

Branch coverage is enabled in `pyproject.toml`. Run the unit suite under coverage in the local environment:

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
python -m coverage run -m pytest \
  -p pytest_asyncio.plugin -p bsworld.plugin tests/unit
python -m coverage report
```

After building the required firmware, run the integration suite separately:

```sh
pytest tests/integration/ -n auto
```

The coverage report includes the complete `bsworld` Python package, including the runtime scheduler.
