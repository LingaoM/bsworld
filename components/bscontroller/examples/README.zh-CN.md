# H4 HCI 扫描示例

[English](README.md) | [简体中文](README.zh-CN.md)

安装该组件，并保留 BabbleSim 构建产生的 `BSIM_OUT_PATH`。在组件目录下运行 `python examples/advertise_scan.py`。该示例将执行扫描的 Controller 暴露为一个承载标准 H4 HCI 数据包的 Unix 套接字。一个 mock Host 连接到该套接字，发送 HCI 初始化命令和被动扫描命令，并读取一条包含预期地址和数据的 LE Advertising Report。该 mock Host 不持有对 Controller 对象的任何引用。

第二个 Controller 通过共享的 BabbleSim PHY 提供 RF 广播。该示例持有两个 Controller、PHY、它自己的离散 Host 时钟，以及一个临时 HCI 套接字；在退出时会关闭并移除这些资源。
