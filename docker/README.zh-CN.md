# BSWorld Docker 测试镜像

[English](README.md) | [中文](README.zh-CN.md)

本目录为 Linux/x86_64 构建完整测试镜像。以下命令均在 BSWorld 仓库根目录执行。

## 镜像内容

[Dockerfile](Dockerfile) 按 BSWorld、BabbleSim、Zephyr、NuttX、QEMU、Buildroot 的顺序准备依赖和编译产物，最后生成独立的 `runtime` 镜像。

最终镜像包含 Python 3.12、BSWorld、pytest、测试用例、BabbleSim 运行组件及 Ellisys 转换脚本、虚拟 Controller、八个 Zephyr 示例、BTSak / NimBLE 两个 NuttX 程序，以及 QEMU、Linux kernel 和 guest rootfs。固件路径已通过镜像环境变量配置。

构建阶段的上游源码、SDK、工具链和中间文件保存在 Docker 构建缓存中。发布时使用最终的 `runtime` 镜像。

## 前置条件

使用 Linux/x86_64 主机，安装 Git 和包含 Buildx 插件的 Docker Engine。Ubuntu 安装步骤见 Docker 官方[安装文档](https://docs.docker.com/engine/install/ubuntu/)，安装后检查：

```sh
sudo docker info
sudo docker buildx version
```

首次使用时，先获取仓库：

```sh
git clone https://github.com/XiaoMi/bsworld.git
cd bsworld
```

## 构建

CI 成功发布后可以[使用已发布镜像](#使用已发布镜像)。本机构建命令如下：

```sh
sudo docker build --progress=plain -f docker/Dockerfile \
  --build-arg BUILD_UID="$(id -u)" \
  --build-arg BUILD_GID="$(id -g)" \
  --build-arg BUILD_JOBS=4 \
  -t bsworld:dev .
```

| 参数 | 用途 | 默认值 |
|---|---|---|
| `BUILD_UID` / `BUILD_GID` | 镜像内 `bsworld` 用户的 UID/GID，本地构建时与当前用户一致 | `1000` / `1000` |
| `BUILD_JOBS` | 固件编译并行度 | `4` |

源码版本和 SDK 选项在 Dockerfile 中配置。首次构建会下载源码、SDK 并编译全部固件；后续构建复用 Docker 层缓存。镜像构建过程中会检查二进制文件及其运行库依赖。

## 使用已发布镜像

CI 从 `main` 发布镜像后，可以使用它测试当前仓库代码：

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

`latest` 指向最近从 `main` 发布且通过测试的环境。需要使用指定环境时，将它替换为对应 CI 运行摘要中的 `env-<hash>` 标签。

## 运行测试

使用本机构建的 `bsworld:dev` 镜像运行内置测试，保存报告和日志：

```sh
mkdir -p .cache/docker-results
sudo docker run --rm \
  --mount "type=bind,src=$PWD/.cache/docker-results,dst=/output" \
  bsworld:dev
```

默认命令为 `pytest tests/integration -n 2 --out-dir /output --junitxml=/output/pytest.xml`。

测试当前仓库的 Python 代码和测试用例：

```sh
sudo docker run --rm \
  --mount "type=bind,src=$PWD,dst=/workspace,readonly" \
  --mount "type=bind,src=$PWD/.cache/docker-results,dst=/output" \
  bsworld:dev
```

选择具体套件：

```sh
sudo docker run --rm \
  --mount "type=bind,src=$PWD,dst=/workspace,readonly" \
  --mount "type=bind,src=$PWD/.cache/docker-results,dst=/output" \
  bsworld:dev \
  pytest tests/integration/zephyr/samples/heart_rate -n 2 \
    --out-dir /output --junitxml=/output/heart-rate.xml
```

运行镜像内的单元测试或静态检查：

```sh
sudo docker run --rm bsworld:dev pytest tests/unit -q
sudo docker run --rm bsworld:dev ruff check src tests
```

## 文件与日志

| 容器路径 | 内容 |
|---|---|
| `/workspace` | BSWorld Python 代码和测试，可挂载本次提交 |
| `/opt/firmware` | Controller、Zephyr、NuttX、QEMU、kernel、rootfs |
| `/opt/babblesim` | BabbleSim 程序、动态模型及转换脚本 |
| `/opt/venv` | BSWorld Python 环境 |
| `/output` | JUnit 报告和按测试生成的日志、抓包文件 |

上述命令把 `/output` 挂载到本机 `.cache/docker-results`。目录需要允许镜像内的 `bsworld` 用户写入；本地构建命令通过 UID/GID 参数保持一致，已发布镜像的示例则为 UID/GID 1000 准备目录权限。CI workflow 会自动准备其结果目录权限。

pytest 的终端输出直接显示在 Docker 调用方的终端或 CI 步骤日志中。默认命令将 pytest 的退出码传递给 `docker run`，CI 据此判定测试成功或失败。workflow 在测试结束后上传结果目录，测试失败时也保留报告与日志。

需要进入容器检查时：

```sh
sudo docker run --rm -it \
  --mount "type=bind,src=$PWD,dst=/workspace,readonly" \
  --mount "type=bind,src=$PWD/.cache/docker-results,dst=/output" \
  bsworld:dev bash
```

本机 Linux 构建见[仓库 README](../docs/zh-CH/README.md#本地-linux)；测试日志结构见[日志文档](../docs/zh-CH/artifacts.md)，第三方组件说明见[第三方声明](../docs/zh-CH/THIRD_PARTY_NOTICES.md)。
