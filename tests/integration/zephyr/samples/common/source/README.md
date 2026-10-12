# Zephyr Sample Build Inputs

[English](README.md) | [中文](README.zh-CN.md)

BSWorld does not copy Zephyr sample source. The test images are built from the stock Applications in an external Zephyr workspace with two local inputs:

- `bsim_host_only.overlay` selects the Unix socket HCI transport.
- `bsim.conf` enables the Host-only BabbleSim runtime settings shared by all samples. Mesh adds `mesh/source/mesh.conf`.

## Prepare the Workspace

The currently validated Zephyr revision is:

```text
35c46048d330ce1bea9248d4dd6a9879d0fe5be7
```

Follow Zephyr's official [Getting Started Guide](https://docs.zephyrproject.org/latest/develop/getting_started/index.html) for host dependencies. A new workspace can be initialized as follows:

```sh
python3.12 -m venv /path/to/zephyrproject/.venv
source /path/to/zephyrproject/.venv/bin/activate
pip install west

west init /path/to/zephyrproject
cd /path/to/zephyrproject
west update
west packages pip --install
west zephyr-export

cd zephyr
west sdk install
```

BabbleSim must already be built at the path passed through `--bsim-out-dir`. See the repository root [README](../../../../../../README.md).

## Build

Use the platform build entry point and pass external paths explicitly:

```sh
/path/to/bsworld/tests/integration/zephyr/samples/build.sh \
  --zephyr-workspace /path/to/zephyrproject \
  --bsim-out-dir /tmp/bsworld/build/babblesim/bsim
```

Before compiling, the script fetches the Zephyr repository, checks out the validated revision, updates the west workspace and Python packages, exports Zephyr, and installs the SDK. It then builds all stock samples and packages each runtime beside its owning test group:

```text
tests/integration/zephyr/samples/<group>/prebuilt/<sample>/exodus/bin/zephyr.exe
```

The repository-wide `scripts/build_all.py` uses the same entry point when producing every BSWorld binary artifact.
