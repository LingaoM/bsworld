# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

"""Test the Python clock against a real BabbleSim PHY, without a Controller."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import uuid

import pytest

from bsworld.deps import check_babblesim_ready
from bsworld.env import Env
from bsworld.runtime.scheduler import BsimClock
from bsworld.runtime.wait import wait_for_path


@pytest.fixture
def phy_clock(tmp_path):
    env = Env.detect()
    check_babblesim_ready(env)
    sim_id = f"bsw_clock_{uuid.uuid4().hex[:12]}"
    with (tmp_path / "phy.log").open("wb") as output:
        phy = subprocess.Popen(
            [env.bsim_bin_dir / "bs_2G4_phy_v1", f"-s={sim_id}", "-D=1", "-nodump"],
            cwd=env.bsim_bin_dir,
            stdout=output,
            stderr=subprocess.STDOUT,
        )
        clock = BsimClock(
            sim_dir=env.sim_dir(sim_id),
            phy_id="2G4",
            dev_id=0,
            phy_alive=lambda: phy.poll() is None,
        )
        try:
            wait_for_path(env.sim_dir(sim_id) / "2G4.phy.lock", timeout=5)
            clock.connect()
            yield clock, phy, env
        finally:
            if phy.poll() is None:
                phy.send_signal(signal.SIGCONT)
            clock.close()
            if phy.poll() is None:
                phy.terminate()
            phy.wait(timeout=5)
            shutil.rmtree(clock.sim_dir, ignore_errors=True)


def test_clock_advances_and_releases_device_resources(phy_clock) -> None:
    clock, _, _ = phy_clock
    lock = clock.sim_dir / "2G4.d0.lock"
    assert lock.is_file()
    clock.synchronize()
    assert clock.now_us == 0
    for target in (1, 1_001, 10_000, 1_000_000):
        assert clock.advance_to_us(target) == target
        clock.synchronize()
        assert clock.now_us == target
    assert clock.advance_to_us(10_000) == 1_000_000
    clock.close()
    clock.close()
    assert not lock.exists()


def test_clock_detects_phy_disconnect(phy_clock) -> None:
    clock, phy, _ = phy_clock
    assert clock.advance_to_us(1_000) == 1_000
    phy.terminate()
    phy.wait(timeout=5)
    with pytest.raises(RuntimeError, match="PHY disconnected"):
        clock.advance_to_us(2_000)
    assert clock.now_us == 1_000


def test_clock_bounds_wall_time_wait_for_unresponsive_phy(phy_clock) -> None:
    clock, phy, _ = phy_clock
    os.kill(phy.pid, signal.SIGSTOP)
    os.waitpid(phy.pid, os.WUNTRACED)
    clock.step_timeout = 0.02
    with pytest.raises(TimeoutError, match="timed out"):
        clock.advance_to_us(1_000)
    assert clock.now_us == 0


@pytest.mark.parametrize("monitor_phy", [False, True])
def test_clock_connection_is_bounded_if_phy_dies_after_creating_fifos(
    tmp_path, monitor_phy
) -> None:
    env = Env.detect()
    check_babblesim_ready(env)
    sim_id = f"bsw_clock_{uuid.uuid4().hex[:12]}"
    with (tmp_path / "phy.log").open("wb") as output:
        phy = subprocess.Popen(
            [env.bsim_bin_dir / "bs_2G4_phy_v1", f"-s={sim_id}", "-D=1", "-nodump"],
            cwd=env.bsim_bin_dir,
            stdout=output,
            stderr=subprocess.STDOUT,
        )
        clock = BsimClock(
            sim_dir=env.sim_dir(sim_id),
            phy_id="2G4",
            dev_id=0,
            phy_alive=(lambda: phy.poll() is None) if monitor_phy else None,
        )
        try:
            wait_for_path(clock.sim_dir / "2G4.d0.ptd", timeout=5)
            phy.kill()
            phy.wait(timeout=5)
            error = RuntimeError if monitor_phy else TimeoutError
            with pytest.raises(error, match="exited|did not connect"):
                clock.connect(timeout=0.02)
            assert not (clock.sim_dir / "2G4.d0.lock").exists()
        finally:
            clock.close()
            if phy.poll() is None:
                phy.kill()
            phy.wait(timeout=5)
            shutil.rmtree(clock.sim_dir, ignore_errors=True)
