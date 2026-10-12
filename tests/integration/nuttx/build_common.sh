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

readonly NUTTX_TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly BSWORLD_ROOT="$(cd "$NUTTX_TESTS_DIR/../../.." && pwd)"
readonly BSWORLD_NUTTX_REVISION="89c4b8ccaf03f1c6d33624d93ef640d8d176a78d"
readonly BSWORLD_NUTTX_APPS_REVISION="8404450fb89346ed244d1c701e5feb5d19f32271"
readonly BSWORLD_NUTTX_REPOSITORY="https://github.com/apache/nuttx.git"
readonly BSWORLD_NUTTX_APPS_REPOSITORY="https://github.com/apache/nuttx-apps.git"
# shellcheck source=scripts/build_helpers.sh
source "$BSWORLD_ROOT/scripts/build_helpers.sh"

nuttx_parse_build_args() {
  NUTTX_DIR=""
  NUTTX_APPS_DIR=""
  BSIM_OUT_DIR=""
  BUILD_JOBS="$(nproc)"
  NUTTX_SKIP_UPDATE=no

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --nuttx-dir) NUTTX_DIR="${2:-}"; shift 2 ;;
      --nuttx-apps-dir) NUTTX_APPS_DIR="${2:-}"; shift 2 ;;
      --bsim-out-dir) BSIM_OUT_DIR="${2:-}"; shift 2 ;;
      --jobs) BUILD_JOBS="${2:-}"; shift 2 ;;
      --skip-nuttx-update) NUTTX_SKIP_UPDATE=yes; shift ;;
      -h | --help) printf '%s\n' "$NUTTX_BUILD_USAGE"; exit 0 ;;
      *) build_die "unknown argument: $1" ;;
    esac
  done

  [[ -n "$NUTTX_DIR" ]] || build_die "--nuttx-dir is required"
  [[ -n "$NUTTX_APPS_DIR" ]] || build_die "--nuttx-apps-dir is required"
  [[ -n "$BSIM_OUT_DIR" ]] || build_die "--bsim-out-dir is required"
  [[ "$BUILD_JOBS" =~ ^[1-9][0-9]*$ ]] || build_die "--jobs must be a positive integer"

  build_require_directory "NuttX" "$NUTTX_DIR"
  build_require_directory "nuttx-apps" "$NUTTX_APPS_DIR"
  build_require_command git
  build_require_command kconfig-tweak
  build_require_command make
  build_require_command objcopy
  build_require_command realpath
  build_require_command strip

  export BSIM_OUT_PATH="$BSIM_OUT_DIR"
  export BSIM_COMPONENTS_PATH="$BSWORLD_ROOT/components/babblesim/components"
  export BSIM_BASE_PATH="$BSIM_COMPONENTS_PATH"
}

nuttx_prepare_sources() {
  local actual_nuttx_revision
  local actual_apps_revision

  if [[ "$NUTTX_SKIP_UPDATE" != yes ]]; then
    if ! git -C "$NUTTX_DIR" diff --quiet ||
      ! git -C "$NUTTX_DIR" diff --cached --quiet; then
      build_die "NuttX checkout has uncommitted tracked changes: $NUTTX_DIR"
    fi
    if ! git -C "$NUTTX_APPS_DIR" diff --quiet ||
      ! git -C "$NUTTX_APPS_DIR" diff --cached --quiet; then
      build_die "nuttx-apps checkout has uncommitted tracked changes: $NUTTX_APPS_DIR"
    fi

    echo "==> Preparing NuttX $BSWORLD_NUTTX_REVISION"
    git -C "$NUTTX_DIR" fetch --prune "$BSWORLD_NUTTX_REPOSITORY"
    git -C "$NUTTX_DIR" fetch "$BSWORLD_NUTTX_REPOSITORY" "$BSWORLD_NUTTX_REVISION"
    git -C "$NUTTX_DIR" checkout --detach "$BSWORLD_NUTTX_REVISION"

    echo "==> Preparing nuttx-apps $BSWORLD_NUTTX_APPS_REVISION"
    git -C "$NUTTX_APPS_DIR" fetch --prune "$BSWORLD_NUTTX_APPS_REPOSITORY"
    git -C "$NUTTX_APPS_DIR" fetch "$BSWORLD_NUTTX_APPS_REPOSITORY" "$BSWORLD_NUTTX_APPS_REVISION"
    git -C "$NUTTX_APPS_DIR" checkout --detach "$BSWORLD_NUTTX_APPS_REVISION"
  fi

  actual_nuttx_revision="$(git -C "$NUTTX_DIR" rev-parse HEAD)"
  if [[ "$actual_nuttx_revision" != "$BSWORLD_NUTTX_REVISION" ]]; then
    build_die "unexpected NuttX revision: $actual_nuttx_revision"
  fi

  actual_apps_revision="$(git -C "$NUTTX_APPS_DIR" rev-parse HEAD)"
  if [[ "$actual_apps_revision" != "$BSWORLD_NUTTX_APPS_REVISION" ]]; then
    build_die "unexpected nuttx-apps revision: $actual_apps_revision"
  fi
}

nuttx_prefix_map_flags() {
  local -a roots=("$NUTTX_DIR" "$NUTTX_APPS_DIR" "$BSWORLD_ROOT")
  local root

  for root in "${roots[@]}"; do
    printf ' -ffile-prefix-map=%s=.' "$root"
    printf ' -fdebug-prefix-map=%s=.' "$root"
    printf ' -fmacro-prefix-map=%s=.' "$root"
  done
}

nuttx_strip_runtime_binary() {
  local executable="$1"

  strip --strip-unneeded "$executable"
  objcopy \
    --remove-section=.comment \
    --remove-section=.GCC.command.line \
    "$executable"
}

nuttx_build() {
  local config="$1"
  local output="$2"
  shift 2

  local apps_relative
  local prefix_map_flags
  apps_relative="$(realpath --relative-to="$NUTTX_DIR" "$NUTTX_APPS_DIR")"
  prefix_map_flags="$(nuttx_prefix_map_flags)"

  (
    cd "$NUTTX_DIR"
    make distclean
    ./tools/configure.sh -l -a "$apps_relative" "sim:$config"
    kconfig-tweak --file .config -e SIM_BSIM_TIME "$@"
    make olddefconfig
    make -j"$BUILD_JOBS" EXTRAFLAGS="$prefix_map_flags"
  )

  nuttx_strip_runtime_binary "$NUTTX_DIR/nuttx"
  build_exodus_runtime "$NUTTX_DIR/nuttx" nuttx "$output"
}
