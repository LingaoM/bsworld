# NuttX BTSak 镜像

[English](README.md) | [中文](README.zh-CN.md)

BTSak 测试直接使用 NuttX 上游自带的 `sim:bthcisock` 配置和 `btsak` 业务程序。BSWorld 不在该测试套件中复制业务程序源码。

## 构建

可以从任意目录执行该测试套件的构建脚本，所有外部源码工作区路径都通过参数明确传入：

```sh
/path/to/bsworld/tests/integration/nuttx/btsak/build.sh \
  --nuttx-dir /path/to/nuttx \
  --nuttx-apps-dir /path/to/nuttx-apps \
  --bsim-out-dir /tmp/bsworld/build/babblesim/bsim
```

脚本使用传入的 nuttx-apps 源码树配置 NuttX，关闭 `CONFIG_BLUETOOTH_SMP_SELFTEST`，启用 `CONFIG_SIM_BSIM_TIME`，并生成：

```text
tests/integration/nuttx/btsak/prebuilt/nuttx/exodus/bin/nuttx
```

这个路径是已经展开的 Exodus 运行目录中的 launcher。

使用 [`../../build.sh`](../../build.sh) 可以构建全部 NuttX 测试套件；`scripts/build_all.py` 可以构建 BSWorld 的全部二进制。
