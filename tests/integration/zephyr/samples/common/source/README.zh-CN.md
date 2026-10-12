# Zephyr 示例程序构建配置

[English](README.md) | [中文](README.zh-CN.md)

BSWorld 不复制 Zephyr 示例程序源码。测试镜像直接使用外部 Zephyr 源码工作区中上游自带的示例构建，只额外叠加两项本地配置：

- `bsim_host_only.overlay` 选择基于 Unix socket 的 HCI 传输方式。
- `bsim.conf` 启用所有示例共用的纯 Host BabbleSim 配置；Mesh 测试还会叠加 `mesh/source/mesh.conf`。

## 准备 Zephyr 源码工作区

当前经过验证的 Zephyr 提交为：

```text
35c46048d330ce1bea9248d4dd6a9879d0fe5be7
```

主机依赖以 Zephyr 官方[入门指南](https://docs.zephyrproject.org/latest/develop/getting_started/index.html)为准。新的源码工作区可以按以下步骤初始化：

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

构建示例程序前，必须先将 BabbleSim 构建到 `--bsim-out-dir` 指定的路径。具体准备方式见仓库的中文 [README](../../../../../../docs/zh-CH/README.md)。

## 构建

调用平台级构建入口，并明确传入所有外部路径：

```sh
/path/to/bsworld/tests/integration/zephyr/samples/build.sh \
  --zephyr-workspace /path/to/zephyrproject \
  --bsim-out-dir /tmp/bsworld/build/babblesim/bsim
```

构建前，脚本会拉取 Zephyr 官方仓库，切换到经过验证的提交，更新 west 工作区和 Python 依赖，执行 Zephyr export，并安装 SDK。随后脚本构建全部上游示例程序，并将每个可执行程序打包到对应测试组：

```text
tests/integration/zephyr/samples/<group>/prebuilt/<sample>/exodus/bin/zephyr.exe
```

仓库级 `scripts/build_all.py` 在生成全部 BSWorld 二进制产物时也会复用这个入口。
