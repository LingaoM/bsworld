# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""ISO BIG commands (issue A).

The ISO command table names the BIG commands "create - big", "sync - big"
and "term - big", so iso create-big, sync-big and term-big are unknown
commands. Behind them, create-big reads a NULL broadcast code for "enc"
without a code, and sync-big accepts too few optional arguments for all
its options.
"""

BROADCAST_CODE = "00112233445566778899aabbccddffff"


async def test_big_commands_are_listed(single):
    out = await single.run("iso", until="Subcommands:")
    for name in ("create-big", "sync-big", "term-big"):
        assert f"  {name} " in out, out


async def test_big_commands_reach_their_handlers(single):
    # Without an advertising set, periodic advertising sync or BIG, each
    # handler stops at its first check.
    await single.run(
        "iso create-big", until="No \\(periodic\\) advertising set selected"
    )
    await single.run("iso sync-big 1", until="No PA sync selected")
    await single.run("iso term-big", until="Unable to terminate BIG")


async def test_big_broadcast_and_sync(pair):
    broadcaster, receiver = pair
    address = await broadcaster.identity()
    await broadcaster.run(
        "bt adv-create nconn-nscan ext-adv identity", until="Created adv id"
    )
    await broadcaster.run("bt per-adv-param")
    await broadcaster.run("iso create-big", until="BIG created")
    await broadcaster.run("bt adv-start", until="set started")
    await broadcaster.run("bt per-adv on", until="Periodic advertising started")

    await receiver.run("bt scan on", until="scan enabled")
    await receiver.run(
        f"bt per-adv-sync-create {address} 0", until="BIG_INFO", timeout=20
    )
    await receiver.run("bt scan off", until="Scan successfully stopped")
    await receiver.run("iso sync-big 1", until=r"ISO Channel \S+ connected", timeout=10)

    await broadcaster.run("iso broadcast", until="ISO broadcasting")
    await receiver.wait("Incoming data channel", timeout=10)

    await broadcaster.run("iso term-big", until="BIG terminated")


async def test_create_big_enc_without_code(single):
    await single.run("bt adv-create nconn-nscan ext-adv", until="Created adv id")
    await single.run("bt per-adv-param")
    # Without a broadcast code, create-big prints its help. Before the fix,
    # the handler passes argv[2] (NULL) to strlen() and the process crashes.
    await single.run("iso create-big enc", until="Create a BIG as a broadcaster")
    await single.run(f"iso create-big enc {BROADCAST_CODE}", until="BIG created")


async def test_sync_big_accepts_all_options(single):
    # No periodic advertising sync exists, so the handler stops at that check.
    # Reaching it shows that the shell accepted the argument count.
    out = await single.run(
        f"iso sync-big 1 mse 2 timeout 100 enc {BROADCAST_CODE}",
        until="No PA sync selected|wrong parameter count|unknown parameter",
    )
    assert "No PA sync selected" in out, out
