# NuttX 测试环境

[English](README.md) | [中文](README.zh-CN.md)

## 准备 NuttX 源码工作区

首次搭建环境时，先参考 Apache NuttX 官方[安装文档](https://nuttx.apache.org/docs/latest/quickstart/install.html)，安装系统依赖、Kconfig 工具和目标工具链。

在 Ubuntu / Debian 上，先安装 NuttX 官方建议的基础依赖：

```sh
sudo apt install -y \
  bison flex gettext texinfo libncurses5-dev libncursesw5-dev xxd \
  git gperf automake libtool pkg-config build-essential genromfs \
  libgmp-dev libmpc-dev libmpfr-dev libisl-dev binutils-dev libelf-dev \
  libexpat1-dev gcc-multilib g++-multilib picocom u-boot-tools util-linux
```

再安装 Kconfig 工具。`kconfig-frontends` 提供 menuconfig 前端以及构建脚本使用的 `kconfig-tweak`；`python3-kconfiglib` 是 NuttX 支持的 Python Kconfig 前端。BSWorld 构建脚本需要 Python 3.12 或更高版本：

```sh
sudo apt install -y \
  kconfig-frontends python3-kconfiglib python3.12 python3.12-venv python3-pip
```

然后准备版本匹配的 NuttX 和 nuttx-apps 源码工作区。两个路径分别传给构建脚本，无需采用固定目录结构：

```sh
git clone https://github.com/apache/nuttx.git /path/to/nuttx
git clone https://github.com/apache/nuttx-apps.git /path/to/nuttx-apps
```

当前验证的版本是：

| 仓库 | Revision |
|---|---|
| NuttX | `89c4b8ccaf03f1c6d33624d93ef640d8d176a78d` |
| nuttx-apps | `8404450fb89346ed244d1c701e5feb5d19f32271` |

每个可独立执行的构建入口都会在编译前从 Apache 官方仓库拉取源码，以 detached HEAD 方式切换到上述提交，并校验最终提交号；本地工作区中 `origin` 的地址不会改变构建所采用的源码来源。如果任一仓库的已跟踪文件存在未提交修改，脚本会在切换版本前停止。

## BSWorld 依赖

构建 BSIM 固件前，需要先按照仓库根目录 README 准备好 BabbleSim 源码和构建输出。构建入口通过 `--bsim-out-dir` 接收 BabbleSim 输出路径，并根据当前仓库位置确定组件源码路径。

## 构建入口

| 套件 | 覆盖内容 | 构建文档 |
|---|---|---|
| BTSak | NuttX 自带的 Bluetooth socket 广播与扫描命令 | [btsak/source/README.zh-CN.md](btsak/source/README.zh-CN.md) |
| NimBLE | NuttX 自带的 NimBLE Central/Peripheral 连接流程 | [nimble/source/README.zh-CN.md](nimble/source/README.zh-CN.md) |

在 BSWorld 仓库根目录构建全部 NuttX 测试镜像：

```sh
tests/integration/nuttx/build.sh \
  --nuttx-dir /path/to/nuttx \
  --nuttx-apps-dir /path/to/nuttx-apps \
  --bsim-out-dir /tmp/bsworld/build/babblesim/bsim
```

`btsak/build.sh` 和 `nimble/build.sh` 接收相同参数，只构建各自负责的测试套件。生成的镜像都会启用 `CONFIG_SIM_BSIM_TIME=y`，并加入 BabbleSim 离散时间。
