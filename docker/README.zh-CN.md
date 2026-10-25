# BSWorld Docker 测试镜像

[English](README.md) | [简体中文](README.zh-CN.md)

镜像包含 Python、BSWorld、测试用例和编译好的固件，可以直接运行内置测试，也可以挂载本地仓库验证自己的代码。修改固件源码或构建配置时，可以使用仓库中的 [Dockerfile](Dockerfile) 重新构建完整测试镜像。

以下命令适用于已安装 [Docker Engine](https://docs.docker.com/engine/install/ubuntu/) 的 Linux/x86_64 主机，Python 和固件运行依赖由镜像提供。命令使用 `sudo` 访问 Docker；当前用户已有 Docker 权限时可以省略。自行构建镜像还需要 Git 和 Docker 的 Buildx 插件。

## 使用已发布镜像

下面的命令可以在任意目录执行，使用镜像内置的代码和集成测试，无需检出源码。公开镜像以 UID/GID 1000 运行，先为它准备可写的结果目录：

```sh
sudo docker pull ghcr.io/xiaomi/bsworld:latest
mkdir -p .cache/docker-results
sudo chown 1000:1000 .cache/docker-results
sudo docker run --rm \
  --mount "type=bind,src=$PWD/.cache/docker-results,dst=/output" \
  -e PYTHONPATH=/workspace \
  ghcr.io/xiaomi/bsworld:latest
```

镜像默认执行 `pytest tests/integration -n 2`，使用两个 worker 运行集成测试。容器中的 `/output` 挂载到当前目录的 `.cache/docker-results`，其中 `pytest.xml` 是测试报告，各测试的日志和抓包也保存在该目录下。`--rm` 会在结束后删除容器，已经写入主机目录的结果会保留。输出结构见[日志文档](../docs/zh-CH/artifacts.md)。

### 选择版本

`latest` 是最近通过测试并发布的主线版本。复现历史源码版本时，将拉取和运行命令中的 `latest` 同时替换为对应的完整 commit ID 或 Release tag：

| 版本 | 镜像地址 |
|---|---|
| 最近通过测试并发布的主线版本 | `ghcr.io/xiaomi/bsworld:latest` |
| 完整 commit ID | `ghcr.io/xiaomi/bsworld:sha-<40位commit>` |
| Release tag | `ghcr.io/xiaomi/bsworld:v1.0.0` |

commit 镜像使用完整的 40 位提交 ID；`v1.0.0` 仅为标签格式示例，请替换为实际已发布的版本。在已有仓库中，也可以读取当前提交 ID 拉取对应镜像（该提交的镜像需已发布）：

```sh
SOURCE_COMMIT="$(git rev-parse HEAD)"
sudo docker pull "ghcr.io/xiaomi/bsworld:sha-$SOURCE_COMMIT"
```

## 运行测试

修改 BSWorld 的 Python 代码或测试用例后，可以复用已发布镜像中的依赖和固件。在仓库根目录执行以下命令，将当前仓库挂载到 `/workspace`，本次测试便使用本地的源码和测试用例：

```sh
mkdir -p .cache/docker-results
sudo chown 1000:1000 .cache/docker-results
sudo docker run --rm \
  --mount "type=bind,src=$PWD,dst=/workspace,readonly" \
  --mount "type=bind,src=$PWD/.cache/docker-results,dst=/output" \
  -e PYTHONPATH=/workspace \
  ghcr.io/xiaomi/bsworld:latest
```

挂载 `/workspace` 后，将使用当前检出版本中的 Python 源码和测试替换镜像内的对应内容。`/workspace` 以只读方式挂载，测试结果通过独立的 `/output` 目录写回主机。固件仍使用镜像内的编译产物，因此 Python 和测试用例的修改可以直接验证；修改 Zephyr、NuttX、QEMU / Buildroot 等固件源码或构建配置后，需要[重新构建镜像](#构建)。

### 选择测试套件

在镜像名后添加命令，会替换默认的集成测试命令。下面只运行 Zephyr heart rate 测试；也可以将路径换成其他测试目录或单个测试文件，并用 `-k` 筛选用例：

```sh
sudo docker run --rm \
  --mount "type=bind,src=$PWD,dst=/workspace,readonly" \
  --mount "type=bind,src=$PWD/.cache/docker-results,dst=/output" \
  -e PYTHONPATH=/workspace \
  ghcr.io/xiaomi/bsworld:latest \
  pytest tests/integration/zephyr/samples/heart_rate -n 2 \
    --out-dir /output --junitxml=/output/heart-rate.xml
```

`--out-dir /output` 指定日志和抓包的输出位置，`--junitxml` 指定测试报告文件；二者都保存在前面挂载的主机目录中。

运行当前检出版本的单元测试：

```sh
sudo docker run --rm \
  --mount "type=bind,src=$PWD,dst=/workspace,readonly" \
  --env PYTHONDONTWRITEBYTECODE=1 \
  -e PYTHONPATH=/workspace \
  ghcr.io/xiaomi/bsworld:latest pytest tests/unit -q -p no:cacheprovider
```

运行 Ruff 静态检查：

```sh
sudo docker run --rm \
  --mount "type=bind,src=$PWD,dst=/workspace,readonly" \
  -e PYTHONPATH=/workspace \
  ghcr.io/xiaomi/bsworld:latest ruff check --no-cache src tests
```

## 构建

需要修改固件、编译配置或镜像依赖时，使用 Dockerfile 自行构建。首次构建会下载依赖并编译固件，后续构建会复用未受修改影响的 Docker 缓存。

BabbleSim 通过 repo 按共用的 [babblesim.xml](../components/babblesim.xml) 版本快照下载，Docker 会在构建时准备源码工作区。

先获取包含 tag 和提交历史的仓库。已有本地仓库时，直接进入仓库根目录：

```sh
git clone https://github.com/XiaoMi/bsworld.git
cd bsworld
```

先构建 `bsworld` 阶段的工具镜像，再通过它从当前仓库的 Git 信息自动读取包版本。这一步只准备 Python 构建环境，还没有编译全部固件：

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

先构建 `python-test` 阶段，在编译固件前完成 lint 和单元测试：

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

检查通过后，构建最终的 `runtime` 镜像，使用相同的包版本。它继承 `python-test` 阶段，构建各固件分支，再加入运行库和编译产物，生成 `bsworld:dev`：

```sh
sudo docker build --progress=plain -f docker/Dockerfile \
  --target runtime \
  --build-arg BUILD_UID="$(id -u)" \
  --build-arg BUILD_GID="$(id -g)" \
  --build-arg BUILD_JOBS=4 \
  --build-arg BSWORLD_VERSION="$BSWORLD_VERSION" \
  -t bsworld:dev .
```

`BUILD_JOBS` 控制编译并行度，可以根据主机资源调整。`BUILD_UID` 和 `BUILD_GID` 让镜像中的运行用户与当前主机用户一致，便于写入挂载的结果目录。上述命令需要在同一个终端中依次执行，以保留 `BSWORLD_VERSION` 变量。

构建阶段按实际依赖拆分，修改无关组件时可以复用已有固件：

```text
build-base
├── bsworld（Python 项目依赖）
│   └── python-test（已安装的项目和测试）
│       └── runtime（加入运行库和下方各分支的固件）
├── babblesim
│   ├── zephyr
│   ├── nuttx
│   ├── qemu
│   └── trouble
└── buildroot（guest 内核和 rootfs）
```

构建完成后，使用本地镜像运行测试：

```sh
mkdir -p .cache/docker-results
sudo chown "$(id -u):$(id -g)" .cache/docker-results
sudo docker run --rm \
  --mount "type=bind,src=$PWD,dst=/workspace,readonly" \
  --mount "type=bind,src=$PWD/.cache/docker-results,dst=/output" \
  -e PYTHONPATH=/workspace \
  bsworld:dev
```

从不含 Git 元数据的源码压缩包构建时，跳过版本读取命令，通过 `BSWORLD_VERSION` 传入已知包版本；省略时使用 `0+local`。

在[测试命令](#运行测试)中，将已发布镜像替换为 `bsworld:dev` 即可。本机 Linux 环境搭建见[仓库 README](../docs/zh-CH/README.md#本地-linux)。
