# NuttX NimBLE 测试

[English](README.md) | [简体中文](README.zh-CN.md)

运行 nuttx-apps 中的 [Apache NimBLE](https://github.com/apache/mynewt-nimble) 示例：`nimble_bleprph` 作为 Peripheral，`nimble_blecent` 作为 Central。Central 扫描、连接、发现服务并订阅通知。构建见 [source/README.zh-CN.md](source/README.zh-CN.md)。

## Shell 命令

Peripheral 进程：

```sh
ifup bnep0
bleprph
```

Central 进程：

```sh
ifup bnep0
blecent
```

## 运行

[Docker 测试镜像](../../../../docker/README.zh-CN.md#选择测试套件)中使用 `tests/integration/nuttx/nimble`。本机运行：

```sh
source "$BSWORLD_ROOT/.venv/bin/activate"
export BSWORLD_NUTTX_NIMBLE_BIN="$NUTTX_NIMBLE_DIR/nuttx"
cd "$BSWORLD_ROOT"
pytest tests/integration/nuttx/nimble -q
```
