#!/usr/bin/env bash
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

set -Eeuo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck source=scripts/build_helpers.sh
source "$ROOT_DIR/scripts/build_helpers.sh"

usage() {
  cat <<'EOF'
usage: components/bt_virt_controller/build.sh \
  --zephyr-workspace PATH \
  --bsim-out-dir PATH \
  [--skip-zephyr-update]
EOF
}

zephyr_workspace=""
bsim_out_dir=""
skip_zephyr_update=no

while [[ $# -gt 0 ]]; do
  case "$1" in
    --zephyr-workspace) zephyr_workspace="${2:-}"; shift 2 ;;
    --bsim-out-dir) bsim_out_dir="${2:-}"; shift 2 ;;
    --skip-zephyr-update) skip_zephyr_update=yes; shift ;;
    -h | --help) usage; exit 0 ;;
    *) build_die "unknown argument: $1" ;;
  esac
done

[[ -n "$zephyr_workspace" ]] || build_die "--zephyr-workspace is required"
[[ -n "$bsim_out_dir" ]] || build_die "--bsim-out-dir is required"
build_require_command strip

export BSIM_OUT_PATH="$bsim_out_dir"
export BSIM_COMPONENTS_PATH="$ROOT_DIR/components/babblesim/components"
export BSIM_BASE_PATH="$BSIM_COMPONENTS_PATH"

build_prepare_zephyr "$zephyr_workspace" "$skip_zephyr_update"

readonly build_dir="$zephyr_workspace/build/bsworld_bt_virt_controller"
(
  cd "$zephyr_workspace"
  west build -p always -b nrf52_bsim \
    -d "$build_dir" \
    "$SCRIPT_DIR"
)

build_exodus_runtime \
  "$build_dir/zephyr/zephyr.exe" \
  bt_virt_controller \
  "$SCRIPT_DIR/prebuilt/bt_virt_controller" \
  yes

echo "Built $SCRIPT_DIR/prebuilt/bt_virt_controller/exodus/bin/bt_virt_controller"
