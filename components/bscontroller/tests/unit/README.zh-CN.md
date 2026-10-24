# BSController 单元测试

[English](README.md) | [简体中文](README.zh-CN.md)

单元套件单独检查 Controller 实现。它无需原生 PHY，也不做协议判定；HCI 与空中传输流程的结果属于 [`../qualification/hci/`](../qualification) 和 `../qualification/ll/`。

下表概括套件所覆盖的内容。

| 范围 | 所保护的不变量 |
|---|---|
| `radio/base`、`linklayer/bitstream`、`linklayer/channel_selection`、`linklayer/parameters`、`linklayer/advertising` | 固定的 wire/CRC/CSA 向量、严格的输入长度、偏移取整、可复现的地址分配与切换边界。 |
| `linklayer/discovery` | 扫描间隙与重叠的 PHY 窗口、退避（backoff）饱和/连续触发，以及跨计数器回绕的信道映射时刻。 |
| `linklayer/scheduler` | 半开区间的预约端点、链式冲突、完整的非抢占时隙，以及相对于请求的调度网格。 |
| `linklayer/link`、`linklayer/primary`、`linklayer/periodic` | 单无线电仲裁、实时身份冲突、饥饿、锚点丢失、获取/已建立（acquisition/established）生命周期转换，以及回调时的上下文替换。 |
| `linklayer/extended` | 依赖报头的容量、感知 PHY 的链间距、身份继承，以及有界/截断的重组。 |
| `linklayer/connection`、`linklayer/control`、`linklayer/data_length` | 队列/ARQ 归属、空的 Host 分片、精确的信用返还、延迟的指示（indication）、重传快照、相互冲突的协商，以及独立的截止期限。 |
| `linklayer/encryption` | 已公布的密码（cipher）向量、TX/RX nonce 耗尽、缓存的加密重试，以及必须持续阻止用户数据的刷新转换。 |
| `hci/controller`、`hci/backend`、`hci/records`、`hci/le` | 解码器/后端隔离、共享句柄发布、实时公共视图，以及跨重新配置的可变广播缓冲区。 |
| `hci/advertising`、`hci/scanning`、`hci/connection`、`hci/events` | 原子化的失败/资源更新、分片暂存、按上下文的命令路由，以及在通知被屏蔽时的状态完成。 |
| `radio/babblesim`、`runtime/session`、`runtime/event_loop`、`runtime/worker` | 分片的 FIFO I/O、错误/延迟的 ACK、时钟准入、就绪工作（ready work）排空、worker 线程归属，以及取消或启动失败后的清理。 |

## 运行

```sh
python -m pytest tests/unit -n auto --dist worksteal -q
```
