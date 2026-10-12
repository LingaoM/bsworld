# NuttX NimBLE 镜像

[English](README.md) | [中文](README.zh-CN.md)

NimBLE 测试直接使用 NuttX 上游自带的 `sim:nimble` 配置，以及 `examples/nimble_bleprph` 和 `examples/nimble_blecent` 业务程序。BSWorld 不复制 NimBLE 业务程序源码。

## 构建

可以从任意目录执行该测试套件的构建脚本，所有外部源码工作区路径都通过参数明确传入：

```sh
/path/to/bsworld/tests/integration/nuttx/nimble/build.sh \
  --nuttx-dir /path/to/nuttx \
  --nuttx-apps-dir /path/to/nuttx-apps \
  --bsim-out-dir /tmp/bsworld/build/babblesim/bsim
```

脚本启用 `CONFIG_SIM_BSIM_TIME`、Peripheral、Central 和 Observer 角色，以及 `nimble_bleprph`、`nimble_blecent` 示例程序，并生成：

```text
tests/integration/nuttx/nimble/prebuilt/nuttx/exodus/bin/nuttx
```

这个路径是已经展开的 Exodus 运行目录中的 launcher。

使用 [`../../build.sh`](../../build.sh) 可以构建全部 NuttX 测试套件；`scripts/build_all.py` 可以构建 BSWorld 的全部二进制。
