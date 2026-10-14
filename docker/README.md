# BSWorld Docker Test Image

[English](README.md) | [中文](README.zh-CN.md)

This directory builds the complete Linux/x86_64 test image. Run all commands below from the BSWorld repository root.

## Image Contents

The [Dockerfile](Dockerfile) prepares dependencies and builds artifacts in BSWorld, BabbleSim, Zephyr, NuttX, QEMU, and Buildroot order, then creates an independent `runtime` image.

The final image includes Python 3.12, BSWorld, pytest, tests, BabbleSim runtime components and the Ellisys converter, the Virtual Controller, eight Zephyr samples, two NuttX BTSak/NimBLE executables, and QEMU with the Linux kernel and guest rootfs. Image environment variables select the firmware paths.

Upstream source, SDKs, toolchains, and intermediate files remain in Docker build caches. Publish the final `runtime` image.

## Prerequisites

Use a Linux/x86_64 host with Git and Docker Engine, including the Buildx plugin. On Ubuntu, follow Docker's [installation instructions](https://docs.docker.com/engine/install/ubuntu/), then verify the installation:

```sh
sudo docker info
sudo docker buildx version
```

For a new checkout:

```sh
git clone https://github.com/XiaoMi/bsworld.git
cd bsworld
```

## Build

The [published image](#use-a-published-image) is available after a successful CI publication. To build locally:

```sh
sudo docker build --progress=plain -f docker/Dockerfile \
  --build-arg BUILD_UID="$(id -u)" \
  --build-arg BUILD_GID="$(id -g)" \
  --build-arg BUILD_JOBS=4 \
  -t bsworld:dev .
```

| Argument | Purpose | Default |
|---|---|---|
| `BUILD_UID` / `BUILD_GID` | UID/GID of the image's `bsworld` user; match the current user when building locally | `1000` / `1000` |
| `BUILD_JOBS` | Firmware compilation parallelism | `4` |

Source revisions and SDK options are configured in the Dockerfile. The first build downloads source/SDKs and compiles all firmware; later builds reuse Docker layers. Image construction checks binaries and their runtime library dependencies.

## Use a Published Image

After CI publishes an image from `main`, run it against the current checkout:

```sh
sudo docker pull ghcr.io/xiaomi/bsworld:latest
mkdir -p .cache/docker-results
# CI images use UID/GID 1000 for the container user.
sudo chown 1000:1000 .cache/docker-results
sudo docker run --rm \
  --mount "type=bind,src=$PWD,dst=/workspace,readonly" \
  --mount "type=bind,src=$PWD/.cache/docker-results,dst=/output" \
  ghcr.io/xiaomi/bsworld:latest
```

`latest` selects the most recently tested environment published from `main`. To use a specific environment, replace it with the `env-<hash>` tag shown in that CI run's summary.

## Run Tests

For a locally built `bsworld:dev` image, run the packaged tests and save reports/logs:

```sh
mkdir -p .cache/docker-results
sudo docker run --rm \
  --mount "type=bind,src=$PWD/.cache/docker-results,dst=/output" \
  bsworld:dev
```

The default command is `pytest tests/integration -n 2 --out-dir /output --junitxml=/output/pytest.xml`.

Test the current checkout's Python source and tests:

```sh
sudo docker run --rm \
  --mount "type=bind,src=$PWD,dst=/workspace,readonly" \
  --mount "type=bind,src=$PWD/.cache/docker-results,dst=/output" \
  bsworld:dev
```

Select a specific suite:

```sh
sudo docker run --rm \
  --mount "type=bind,src=$PWD,dst=/workspace,readonly" \
  --mount "type=bind,src=$PWD/.cache/docker-results,dst=/output" \
  bsworld:dev \
  pytest tests/integration/zephyr/samples/heart_rate -n 2 \
    --out-dir /output --junitxml=/output/heart-rate.xml
```

Run unit tests or lint against the code packaged in the image:

```sh
sudo docker run --rm bsworld:dev pytest tests/unit -q
sudo docker run --rm bsworld:dev ruff check src tests
```

## Files and Logs

| Container path | Contents |
|---|---|
| `/workspace` | BSWorld Python source and tests; mount the commit under test here |
| `/opt/firmware` | Controller, Zephyr, NuttX, QEMU, kernel, and rootfs |
| `/opt/babblesim` | BabbleSim programs, dynamic models, and trace converter |
| `/opt/venv` | BSWorld Python environment |
| `/output` | JUnit reports and per-test logs/captures |

The commands above mount `/output` at the host's `.cache/docker-results`. This directory must be writable by the image's `bsworld` user. Local builds match UID/GID through the build arguments; the published-image example prepares the directory for UID/GID 1000. The CI workflow prepares its result-directory permissions automatically.

Pytest terminal output appears in the caller's terminal or CI step logs. The default command passes pytest's exit code through `docker run`, allowing CI to determine success or failure. The workflow uploads its result directory after testing, including on test failure.

Open a shell for inspection:

```sh
sudo docker run --rm -it \
  --mount "type=bind,src=$PWD,dst=/workspace,readonly" \
  --mount "type=bind,src=$PWD/.cache/docker-results,dst=/output" \
  bsworld:dev bash
```

For native Linux builds, see the [repository README](../README.md#local-linux). See [Logs and captures](../docs/artifacts.md) for the output layout and [Third-Party Notices](../THIRD_PARTY_NOTICES.md) for component notices.
