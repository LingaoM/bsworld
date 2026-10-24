# BSController 架构

[English](architecture.md) | [简体中文](architecture.zh-CN.md)

本文说明 BSController 的分层方式以及数据流动路径，便于集成与调试。协议行为遵循 Bluetooth Core 6.3，受支持的功能特性列于[组件 README](../README.zh-CN.md)。

## 分层

BSController 向 Host 提供标准 HCI 边界，向无线介质提供 BabbleSim PHY 边界。在两者之间运行三个协议层，另有一个驱动仿真时钟的运行时。

```text
Host  ──H4 HCI 字节──►  HCI  ──►  Link Layer  ──►  Radio  ──FIFO──►  BabbleSim PHY
      ◄──H4 HCI 字节──       ◄──            ◄──            ◄──FIFO──
```

| 层 | 负责的边界 | 职责 |
|---|---|---|
| **HCI** | 面向 Host 的 H4 传输 | 对 HCI 命令成帧并校验，在解码前拒绝不受支持的命令，将线上单位转换为 Link Layer 数值，并将 Link Layer 通知编码为 HCI 事件（应用事件掩码、重复过滤和上报分片）。 |
| **Link Layer** | 内部协议状态 | 负责 advertising、scanning、initiation、周期同步、ACL 连接状态、LL control 流程、加密、信道选择以及 radio 时隙调度。 |
| **Radio** | 面向 PHY 的 FIFO | 对外暴露发送、接收与物理时间服务，并适配到 BabbleSim 的 FIFO 协议与 RF 参数。 |
| **Runtime** | 线程、时钟、进程 | 组合 worker 线程、仿真时间事件循环、会话生命周期以及 BabbleSim PHY 进程。 |

分层是单向的：Link Layer 不依赖 HCI。共享原语（设备地址、Controller 错误码、序列化辅助工具）位于两层之下，HCI 重新导出用于数据包构造的共享协议类型。

## 命令与事件流

一条 Host 命令及其响应会穿过所有层：

1. Host 向 Unix socket 写入一条 H4 HCI 命令（进程内则调用 `on_packet`）。
2. HCI 对数据包成帧，过滤不受支持的命令，并校验参数。无效或不受支持的命令会返回带有 Controller 错误码的 Command Complete 或 Command Status，而不会到达 Link Layer。
3. 对于接受的命令，HCI 转换线上单位（例如将 10 ms 的 supervision 字段转换为内部微秒），并调用对应的 Link Layer 操作。
4. Link Layer 更新协议状态并调度 radio 工作。
5. Link Layer 通知回流到 HCI，HCI 应用事件掩码与重复过滤，对 advertising 上报进行分片，并向 Host 发出 HCI 事件。

## Radio 与仿真时间

Link Layer 向其调度器请求发送与接收时隙，调度器强制执行不重叠、非抢占的预留。Radio 层将这些时隙渲染为 BabbleSim FIFO 请求，并从 PHY 接收结果、数据与时间戳。

所有射频时间以整数微秒表示。每个 worker 维护自己的时钟端点，通过 PHY 同步到共同的仿真时间线；若使用独立 Host 时钟，其 PHY 设备编号需与所有 Controller 区分开。window widening、保护间隔以及 LE inter-frame space 等时序均以仿真时间定义，因此主机负载只改变执行耗时，而不改变协议时间线。线程、时钟与资源归属见[组件 README](../README.zh-CN.md#线程时钟与资源生命周期)。

## 实现限制

以下内容有意不予实现，会影响 Host 或测试可以预期的行为：

- 无隐私地址生成、SMP 配对协议或密钥数据库。仅提供 AES `e`，用于 HCI Encrypt 与 LL 会话密钥派生。
- 无 L2CAP 重组、BR/EDR/LMP 执行或 GAP advertising-data 解析。HCI/LL 处理原始载荷，更高层的组装由 Host 负责。
- 无 LocalLink 回退，也无 Controller 到 Controller 的直接投递。所有 Controller 都通过共享 PHY 交互。
- 资源容量与受支持的 PHY 掩码是本实现的能力，而非规范性的 Bluetooth 最大值。

## 规范参考

- [Vol 1, Part A, 2: Core system architecture](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core_v6.3/out/en/architecture,-change-history,-and-conventions/architecture.html)：Host、Controller、resource manager、Link Controller 与 PHY 的职责划分。
- [Vol 1, Part F: Controller Error Codes](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core_v6.3/out/en/architecture,-change-history,-and-conventions/controller-error-codes.html)。
- [Vol 4, Part E: HCI functional specification](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core_v6.3/out/en/host-controller-interface/host-controller-interface-functional-specification.html)。
- [Vol 6, Part A: Radio Physical Layer](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core_v6.3/out/en/low-energy-controller/radio-physical-layer-specification.html)。
- [Vol 6, Part B: Link Layer](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core_v6.3/out/en/low-energy-controller/link-layer-specification.html)。
- [Vol 6, Part E: Low Energy Link Layer Security](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core_v6.3/out/en/low-energy-controller/low-energy-link-layer-security.html)。
