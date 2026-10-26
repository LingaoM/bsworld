# BSWorld Docker Test Image

[English](README.md) | [简体中文](README.zh-CN.md)

Use the published image to run BSWorld tests directly. It includes Python, BSWorld, tests, and compiled firmware. Build your own image when changing firmware source or build configuration.

Use a Linux/x86_64 host with [Docker Engine](https://docs.docker.com/engine/install/ubuntu/). Python, component SDKs, and toolchains do not need to be installed on the host. Local development also requires Git, and image builds require Docker's Buildx plugin. The commands use `sudo`; omit it if your user already has Docker access.

## Use a Published Image

Pull and run the packaged integration tests from any directory; no source checkout is required:

```sh
sudo docker pull ghcr.io/xiaomi/bsworld:latest
mkdir -p .cache/docker-results
# The published image runs as UID/GID 1000.
sudo chown 1000:1000 .cache/docker-results
sudo docker run --rm \
  --mount "type=bind,src=$PWD/.cache/docker-results,dst=/output" \
  -e PYTHONPATH=/workspace \
  ghcr.io/xiaomi/bsworld:latest
```

The default command runs all integration tests with two parallel workers (`pytest tests/integration -n 2`). The writable `/output` mount saves reports, logs, and captures under the host's `.cache/docker-results`; `pytest.xml` is the test report. `--rm` removes the container after it exits, while these files remain on the host. See [Logs and captures](../docs/artifacts.md) for the output layout.

### Select a Version

`latest` is the most recently published tested main image. To reproduce an older source revision, replace `latest` in both the pull and run commands with a matching commit or Release image:

| Version | Image reference |
|---|---|
| Latest tested main | `ghcr.io/xiaomi/bsworld:latest` |
| Full commit ID | `ghcr.io/xiaomi/bsworld:sha-<40-character-commit>` |
| Release tag | `ghcr.io/xiaomi/bsworld:v1.0.0` |

Commit images use the full 40-character commit ID; `v1.0.0` only illustrates the tag format, so replace it with an available Release tag. From an existing checkout, derive the current commit's image (it must already be published):

```sh
SOURCE_COMMIT="$(git rev-parse HEAD)"
sudo docker pull "ghcr.io/xiaomi/bsworld:sha-$SOURCE_COMMIT"
```

## Run Tests

To test your own Python code and tests, run from the repository root and mount it at `/workspace`:

```sh
mkdir -p .cache/docker-results
sudo chown 1000:1000 .cache/docker-results
sudo docker run --rm \
  --mount "type=bind,src=$PWD,dst=/workspace,readonly" \
  --mount "type=bind,src=$PWD/.cache/docker-results,dst=/output" \
  -e PYTHONPATH=/workspace \
  ghcr.io/xiaomi/bsworld:latest
```

The `/workspace` mount replaces the image's Python source and tests with your checkout. `readonly` lets the container read those files without modifying them; test output goes to the separate writable `/output` mount.

Python and test changes can be checked this way without rebuilding. Firmware still comes from the image, so firmware source or build configuration changes require [rebuilding it](#build).

### Select a Suite

To select a suite, put a pytest command after the image name. It replaces the image's default command:

```sh
sudo docker run --rm \
  --mount "type=bind,src=$PWD,dst=/workspace,readonly" \
  --mount "type=bind,src=$PWD/.cache/docker-results,dst=/output" \
  -e PYTHONPATH=/workspace \
  ghcr.io/xiaomi/bsworld:latest \
  pytest tests/integration/zephyr/shell -n 2 \
    --out-dir /output --junitxml=/output/zephyr-shell.xml
```

`-n 2` uses two test workers. `--out-dir` selects the log and capture directory; `--junitxml` writes the test report. Paths under `/output` appear in `.cache/docker-results` on the host.

Run unit tests against the current checkout:

```sh
sudo docker run --rm \
  --mount "type=bind,src=$PWD,dst=/workspace,readonly" \
  --env PYTHONDONTWRITEBYTECODE=1 \
  -e PYTHONPATH=/workspace \
  ghcr.io/xiaomi/bsworld:latest pytest tests/unit -q -p no:cacheprovider
```

Run Ruff for static checks:

```sh
sudo docker run --rm \
  --mount "type=bind,src=$PWD,dst=/workspace,readonly" \
  -e PYTHONPATH=/workspace \
  ghcr.io/xiaomi/bsworld:latest ruff check --no-cache src tests
```

## Build

BabbleSim is fetched with repo using the shared [babblesim.xml](../components/babblesim.xml) version snapshot. Docker prepares its source workspace during the build.

Clone the repository with its tags and history, then run the remaining commands from its root:

```sh
git clone https://github.com/XiaoMi/bsworld.git
cd bsworld
```

Prepare the Python tooling target, then read the package version automatically from Git with `setuptools-scm`:

```sh
sudo docker build --progress=plain -f docker/Dockerfile \
  --target bsworld -t bsworld:tooling \
  --build-arg BUILD_UID="$(id -u)" \
  --build-arg BUILD_GID="$(id -g)" .
BSWORLD_VERSION="$(sudo docker run --rm \
  --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$PWD,dst=/workspace,readonly" \
  --env PYTHONDONTWRITEBYTECODE=1 --env GIT_OPTIONAL_LOCKS=0 \
  bsworld:tooling python -m setuptools_scm)"
```

Build the `python-test` target and run lint and unit tests before compiling firmware:

```sh
sudo docker build --progress=plain -f docker/Dockerfile \
  --target python-test \
  --build-arg BUILD_UID="$(id -u)" \
  --build-arg BUILD_GID="$(id -g)" \
  --build-arg BSWORLD_VERSION="$BSWORLD_VERSION" \
  -t bsworld:python-test .
sudo docker run --rm --env PYTHONDONTWRITEBYTECODE=1 \
  bsworld:python-test python -m ruff check --no-cache src tests
sudo docker run --rm --env PYTHONDONTWRITEBYTECODE=1 \
  bsworld:python-test python -m pytest tests/unit -q -p no:cacheprovider
```

After these checks pass, build the complete runtime image using the same [Dockerfile](Dockerfile). It extends `python-test`, builds the firmware branches, and adds their outputs and runtime libraries:

```sh
sudo docker build --progress=plain -f docker/Dockerfile \
  --target runtime \
  --build-arg BUILD_UID="$(id -u)" \
  --build-arg BUILD_GID="$(id -g)" \
  --build-arg BUILD_JOBS=4 \
  --build-arg BSWORLD_VERSION="$BSWORLD_VERSION" \
  -t bsworld:dev .
```

`BUILD_UID` and `BUILD_GID` match the image user to your host user so generated files have the expected ownership. Adjust `BUILD_JOBS` for compilation parallelism. The first build downloads dependencies and compiles firmware; later builds reuse Docker's cache.

The build stages have independent dependencies so unrelated changes can reuse compiled firmware:

```text
build-base
├── bsworld (Python project dependencies)
│   └── python-test (installed project and tests)
│       └── runtime (+ runtime libraries and firmware from the branches below)
├── babblesim
│   ├── zephyr
│   ├── nuttx
│   ├── qemu
│   └── trouble
└── buildroot (guest kernel and rootfs)
```

Run the locally built image. Restore ownership of the output directory if it was previously prepared for the published image's UID/GID 1000:

```sh
mkdir -p .cache/docker-results
sudo chown "$(id -u):$(id -g)" .cache/docker-results
sudo docker run --rm \
  --mount "type=bind,src=$PWD,dst=/workspace,readonly" \
  --mount "type=bind,src=$PWD/.cache/docker-results,dst=/output" \
  -e PYTHONPATH=/workspace \
  bsworld:dev
```

For a source archive without Git metadata, pass the known package version as `BSWORLD_VERSION` instead of running the version command; omitting it uses `0+local`.

Use `bsworld:dev` in place of the published image in the [test commands](#run-tests). For native Linux setup, see the [repository README](../README.md#local-linux).
