# BSWorld NuttX BTSak 测试

[English](README.md) | [简体中文](README.zh-CN.md)

运行 NuttX 自带的 `btsak`，通过 shell 命令让每个进程充当广播者或扫描者。构建见 [source/README.zh-CN.md](source/README.zh-CN.md)。

## Shell 命令

广播进程：

```sh
ifup bnep0
bt bnep0 advertise start
```

扫描进程：

```sh
ifup bnep0
bt bnep0 scan start
sleep 1
bt bnep0 scan get
...
```

## 测试用例

- `test_nuttx_btsak_scanner_finds_advertiser`：一个扫描者发现一个广播者。
- `test_nuttx_btsak_shell_commands_can_stage_scan`：先启动两个 shell，再分阶段下发角色命令。
- `test_nuttx_btsak_scanner_finds_multiple_advertisers`：一个扫描者发现两个广播者。
- `test_nuttx_btsak_targeted_interference_isolates_and_recovers`：广播信道上的 CW 干扰只阻断一个扫描者，干扰结束后恢复。

## 运行

[Docker 测试镜像](../../../../docker/README.zh-CN.md#选择测试套件)中使用 `tests/integration/nuttx/btsak`。本机运行：

```sh
source "$BSWORLD_ROOT/.venv/bin/activate"
export BSWORLD_NUTTX_BTSAK_BIN="$NUTTX_DIR/nuttx"
cd "$BSWORLD_ROOT"
pytest tests/integration/nuttx/btsak -q
```
