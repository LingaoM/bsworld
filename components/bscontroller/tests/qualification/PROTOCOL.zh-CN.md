# RadioController 协议测试

[English](PROTOCOL.md) | [简体中文](PROTOCOL.zh-CN.md)

本测试套件按照实际的 HCI 和 LL 测试套件章节组织。这些测试并不表示已通过 Bluetooth SIG（蓝牙技术联盟）的资格认定或获得认证。

## 章节布局

本套件包含 17 个主测试文件：九个 HCI 章节和八个 LL 章节。每个来源过程（source procedure）对应一个测试方法；其各测试用例变体是该方法的参数。印刷页码标签不是章节编号。

| 目录 | 来源章节 | 测试文件 | 选取用例数 |
|---|---|---|---:|
| `hci/` | 4.3 Generic Events | `generic_events_test.py` | 5 |
| `hci/` | 4.4 Device Setup | `device_setup_test.py` | 5 |
| `hci/` | 4.5 Controller Flow Control | `controller_flow_control_test.py` | 1 |
| `hci/` | 4.6 Controller Information | `controller_information_test.py` | 5 |
| `hci/` | 4.7 Device Discovery | `device_discovery_test.py` | 68 |
| `hci/` | 4.8 Host Flow Control | `host_flow_control_test.py` | 1 |
| `hci/` | 4.10 Controller Configuration | `controller_configuration_test.py` | 13 |
| `hci/` | 4.13 LE Connection Management | `connection_management_test.py` | 6 |
| `hci/` | 4.17 Event Versioning | `event_versioning_test.py` | 5 |
| `ll/` | 4.2 Device Discovery | `device_discovery_test.py` | 113 |
| `ll/` | 4.3 Connection | `connection_test.py` | 197 |
| `ll/` | 4.4 Timing | `timing_test.py` | 21 |
| `ll/` | 4.5 Encoding | `encoding_test.py` | 7 |
| `ll/` | 4.6 Frequency Hopping | `frequency_hopping_test.py` | 6 |
| `ll/` | 4.7 Packet Handling | `packet_handling_test.py` | 6 |
| `ll/` | 4.8 Security | `security_test.py` | 38 |
| `ll/` | 4.9 Data Flow | `data_flow_test.py` | 4 |

各章节用例合计为 109 个 HCI 用例和 392 个 LL 用例，共 501 个选取用例。额外的回归（regression）用例不会增加对这些选取用例的覆盖范围。

## 结果含义

完成其断言的无标记过程会产生一个协议 `PASS`（通过）裁决。两个独立的 pytest 标记（marker）用于描述执行限制，并对应 `PARTIAL`（部分通过）裁决：

- `limited` 保留给亚微秒级的激励或测量精度场景。这些用例以 1 微秒分辨率执行所有可用的检查，采用文档中记录的整数微秒近似值。仅凭定时精度绝不允许跳过；执行器会拒绝来自仅因定时限制的 `limited` 过程的跳过。
- `source_conflict` 标识未解决的来源过程、分支或裁决（verdict）要求。它允许跳过未解决的来源路径，并不意味着 Controller 存在能力缺失。

一个用例可以同时带有这两个标记；混合用例可以因其独立的来源问题而跳过。成功的带标记执行会产生一个 pytest 通过结果和一个协议 `PARTIAL` 裁决，从而保留精度或来源资格的边界。近似执行绝不能被表示为精确的分数微秒测量结果。

没有可执行过程的用例会带有明确的 pytest skip（跳过）原因。`not_applicable`（不适用）与 `unsupported`（不受支持）不同：前者意味着该用例的适用性条件对本 Controller 为假。例如，`HCI/DDI/BI-03-C` 要求 Controller 不支持 LE Set Periodic Advertising Receive Enable，而本 Controller 支持该命令，故该用例不适用。

这些独立实现的测试并不意味着对 LL.TS/HCI.TS 的完整覆盖。

## 运行

```sh
export BSIM_OUT_PATH=/path/to/bsim/build
python -m pytest tests/qualification -n auto --dist worksteal -v -rs

# 运行协议测试和实现单元测试。
python -m pytest tests/ -n auto --dist worksteal -v -rs

# 原生 PHY 可用时，仅受精度限制的用例必须实际执行。
python -m pytest tests/qualification -m 'limited and not source_conflict' -v

# 包含仅有来源冲突和混合限制的用例；未解决的来源路径可以跳过。
python -m pytest tests/qualification -m source_conflict -v -rs
```

## 限制

`BSIM_SCAN_MAX_CODED_RANGE_M` 为 Coded（编码 PHY）最新扫描器用例声明了以米为单位的模拟 `TSPX_scan_max_coded_range`。对于同地协同的模拟端点，其默认值为 0。该激励在将合并的响应延迟取整为整数微秒之前，会先应用来源规定的半微秒范围延迟下限，并将该声明记录到协议日志中。

并行用例拥有独立的 PHY 进程、仿真 ID、FIFO 和日志目录，因此不同仿真中的相同信道无法相互干扰。各 worker 共享主机资源；某些来源过程仍然耗时较长，因为它们需要重复完整地观测数据包，或需要模拟的静默窗口。并行调度不会改变每个用例的步骤、仿真定时和裁决要求。关于安装和 worker 选择，参见[并行执行](../README.zh-CN.md#并行执行)。

## 许可证

版权所有 2026 Xiaomi Corporation。基于 Apache License 2.0 许可；参见 [LICENSE](../../LICENSE)。
