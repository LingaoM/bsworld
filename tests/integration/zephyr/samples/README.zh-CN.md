# Zephyr Bluetooth 示例测试

[English](README.md) | [中文](README.zh-CN.md)

这些测试将未经修改的 Zephyr Bluetooth 示例程序作为独立的 Host 进程接入 BSWorld。公共配置和 devicetree overlay 让每个 Host 通过 Unix socket 连接到独立的虚拟 Controller。

| 测试目录 | Zephyr 示例程序 | 覆盖内容 |
|---|---|---|
| `broadcast_observe/` | `broadcaster`、`observer` | 广播、被动扫描，以及覆盖三个广播信道的定向干扰与恢复 |
| `heart_rate/` | `peripheral_hr`、`central_hr` | 连接、GATT 发现和通知 |
| `periodic_advertising/` | `periodic_adv`、`periodic_sync` | 周期广播同步 |
| `mesh/` | `mesh`、`mesh_provisioner` | Mesh 配网和配置模型控制 |

每个目录管理自己的 Python 测试、进程配置、可选构建片段、构建入口和生成并展开的 `prebuilt/` 运行目录。测试不依赖交互式 Zephyr Shell。

## 构建

先按照 [`common/source/README.zh-CN.md`](common/source/README.zh-CN.md)准备 Zephyr 和 BabbleSim，再构建全部示例镜像：

```sh
tests/integration/zephyr/samples/build.sh \
  --zephyr-workspace /path/to/zephyrproject \
  --bsim-out-dir /tmp/bsworld/build/babblesim/bsim
```

只构建某一组测试时，执行该目录自己的入口，参数保持一致：

```sh
tests/integration/zephyr/samples/heart_rate/build.sh \
  --zephyr-workspace /path/to/zephyrproject \
  --bsim-out-dir /tmp/bsworld/build/babblesim/bsim
```

展开后的 Exodus 运行目录会写入对应测试组的 `prebuilt/<sample>/`。该目录被 Git 忽略，测试中的进程配置会直接执行其中的 launcher。

## 运行

```sh
pytest tests/integration/zephyr/samples -q --no-ellisys
```
