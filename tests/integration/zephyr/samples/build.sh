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
readonly ROOT_DIR="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
# shellcheck source=scripts/build_helpers.sh
source "$ROOT_DIR/scripts/build_helpers.sh"

usage() {
  cat <<'EOF'
usage: tests/integration/zephyr/samples/build.sh \
  --zephyr-workspace PATH \
  --bsim-out-dir PATH \
  [--sample NAME]... \
  [--skip-zephyr-update]
EOF
}

zephyr_workspace=""
bsim_out_dir=""
skip_zephyr_update=no
declare -a samples=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --zephyr-workspace) zephyr_workspace="${2:-}"; shift 2 ;;
    --bsim-out-dir) bsim_out_dir="${2:-}"; shift 2 ;;
    --sample) samples+=("${2:-}"); shift 2 ;;
    --skip-zephyr-update) skip_zephyr_update=yes; shift ;;
    -h | --help) usage; exit 0 ;;
    *) build_die "unknown argument: $1" ;;
  esac
done

[[ -n "$zephyr_workspace" ]] || build_die "--zephyr-workspace is required"
[[ -n "$bsim_out_dir" ]] || build_die "--bsim-out-dir is required"
if [[ ${#samples[@]} -eq 0 ]]; then
  samples=(
    broadcaster observer
    peripheral_hr central_hr
    periodic_adv periodic_sync
    mesh mesh_provisioner
  )
fi

export BSIM_OUT_PATH="$bsim_out_dir"
export BSIM_COMPONENTS_PATH="$ROOT_DIR/components/babblesim/components"
export BSIM_BASE_PATH="$BSIM_COMPONENTS_PATH"

build_prepare_zephyr "$zephyr_workspace" "$skip_zephyr_update"

prefix_map_flags="-ffile-prefix-map=$zephyr_workspace=. \
-fdebug-prefix-map=$zephyr_workspace=. \
-fmacro-prefix-map=$zephyr_workspace=. \
-ffile-prefix-map=$ROOT_DIR=. \
-fdebug-prefix-map=$ROOT_DIR=. \
-fmacro-prefix-map=$ROOT_DIR=."

strip_runtime_binary() {
  local executable="$1"

  build_require_executable "runtime input" "$executable"
  strip --strip-unneeded "$executable"
  objcopy \
    --remove-section=.comment \
    --remove-section=.GCC.command.line \
    "$executable"
}

sample_group() {
  case "$1" in
    broadcaster | observer) printf '%s' broadcast_observe ;;
    peripheral_hr | central_hr) printf '%s' heart_rate ;;
    periodic_adv | periodic_sync) printf '%s' periodic_advertising ;;
    mesh | mesh_provisioner) printf '%s' mesh ;;
    *) build_die "unknown Zephyr sample: $1" ;;
  esac
}

for sample in "${samples[@]}"; do
  group="$(sample_group "$sample")"
  build_dir="$zephyr_workspace/build/bsworld_zephyr_$sample"
  extra_conf="$SCRIPT_DIR/common/source/bsim.conf"
  if [[ "$group" == mesh ]]; then
    extra_conf="$extra_conf;$SCRIPT_DIR/mesh/source/mesh.conf"
  fi

  echo "==> Building Zephyr $sample"
  (
    cd "$zephyr_workspace"
    west build -p always -b nrf52_bsim \
      -d "$build_dir" \
      "$zephyr_workspace/zephyr/samples/bluetooth/$sample" \
      -- \
      -DEXTRA_CONF_FILE="$extra_conf" \
      -DDTC_OVERLAY_FILE="$SCRIPT_DIR/common/source/bsim_host_only.overlay" \
      -DEXTRA_CFLAGS="$prefix_map_flags" \
      -DEXTRA_CXXFLAGS="$prefix_map_flags"
  )

  strip_runtime_binary "$build_dir/zephyr/zephyr.exe"
  build_exodus_runtime \
    "$build_dir/zephyr/zephyr.exe" \
    zephyr.exe \
    "$SCRIPT_DIR/$group/prebuilt/$sample"
done
