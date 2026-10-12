# Copyright 2026 Xiaomi Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
from __future__ import annotations

from pathlib import Path

from bsworld.env import Env, build_root


def test_detect_uses_shared_tmp_build_root() -> None:
    env = Env.detect(out_tag="/tmp/out", now_tag="run-fixed", run_uid="uid")

    assert build_root() == Path("/tmp/bsworld/build")
    assert env.babblesim_root == Path(__file__).parents[2] / "components" / "babblesim"
    assert env.babblesim_components_dir == (
        Path(__file__).parents[2] / "components" / "babblesim" / "components"
    )
    assert env.hci_virt_bin == (
        Path(__file__).parents[2]
        / "components"
        / "bt_virt_controller"
        / "prebuilt"
        / "bt_virt_controller"
        / "exodus"
        / "bin"
        / "bt_virt_controller"
    )
    assert env.bsim_dir == Path("/tmp/bsworld/build/babblesim/bsim")
    assert env.bsim_bin_dir == Path("/tmp/bsworld/build/babblesim/bsim/bin")
