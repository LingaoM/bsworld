# Bumble 集成测试

[English](README.md) | [中文](README.zh-CN.md)

这组测试将 [Bumble](https://github.com/google/bumble) Bluetooth Host 协议栈直接运行在 pytest 的 asyncio event loop 中。每个 Bumble 设备都会分配一个独立的 BSWorld 虚拟 Controller，并通过 Unix-socket HCI 连接。整个过程不需要修改 Bumble 源码，也不需要构建固件镜像。

当前覆盖以下场景：

- 传统广播和被动扫描；
- 覆盖三个广播信道的定向 CW 干扰、空间隔离和干扰后恢复；
- Bumble Central 与 Peripheral 建立连接；
- 扩展周期广播、周期同步和周期广播报告接收。

安装 BSWorld 时会同时安装经过验证的 Bumble 版本：

```sh
python -m pip install -e .
```

按照仓库 README 准备 BabbleSim 并安装 BSWorld 二进制 Release 后，可以直接运行：

```sh
pytest tests/integration/bumble -n auto
```

业务程序直接运行在 pytest 中，因此它们的定时器、socket 操作和超时都会使用测试所用的仿真时间 asyncio event loop；虚拟 Controller 仍然是相互独立的 Linux 进程。每个设备的 BTSnoop 文件保存在该测试的 `bumble/<角色>/` 日志目录中，RF 交互则写入共享的 BabbleSim 跟踪文件。
