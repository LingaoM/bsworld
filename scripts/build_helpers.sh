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

readonly BSWORLD_ZEPHYR_REVISION="35c46048d330ce1bea9248d4dd6a9879d0fe5be7"
readonly BUILD_HELPERS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

build_die() {
  echo "$*" >&2
  exit 2
}

build_require_command() {
  command -v "$1" >/dev/null 2>&1 || build_die "required command not found: $1"
}

build_require_directory() {
  [[ -d "$2" ]] || build_die "$1 directory not found: $2"
}

build_require_executable() {
  [[ -n "$2" && -x "$2" ]] || build_die "$1 executable not found: $2"
}

build_exodus_runtime() {
  local executable="$1"
  local launcher="$2"
  local output="$3"
  local strip_binary="${4:-no}"
  local python_bin="${BSWORLD_PYTHON:-python3.12}"
  local -a args

  build_require_executable "runtime input" "$executable"
  build_require_command "$python_bin"
  args=(
    "$python_bin" "$BUILD_HELPERS_DIR/create_exodus_runtime.py"
    "$executable"
    --launcher "$launcher"
    --output "$output"
  )
  if [[ "$strip_binary" == yes ]]; then
    args+=(--strip)
  fi
  "${args[@]}"
}

build_prepare_zephyr() {
  local workspace="$1"
  local skip_update="${2:-no}"
  local zephyr_base="$workspace/zephyr"
  local revision

  build_require_directory "Zephyr workspace" "$workspace"
  build_require_directory "Zephyr" "$zephyr_base"

  if [[ -f "$workspace/.venv/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "$workspace/.venv/bin/activate"
  fi

  build_require_command git
  build_require_command west

  if [[ "$skip_update" != yes ]]; then
    if ! git -C "$zephyr_base" diff --quiet ||
      ! git -C "$zephyr_base" diff --cached --quiet; then
      build_die "Zephyr checkout has uncommitted tracked changes: $zephyr_base"
    fi

    echo "==> Preparing Zephyr $BSWORLD_ZEPHYR_REVISION"
    git -C "$zephyr_base" fetch --prune origin
    git -C "$zephyr_base" checkout --detach "$BSWORLD_ZEPHYR_REVISION"

    (
      cd "$workspace"
      west update
      west packages pip --install
      west zephyr-export

      cd "$zephyr_base"
      west sdk install
    )
  fi

  revision="$(git -C "$zephyr_base" rev-parse HEAD)"
  if [[ "$revision" != "$BSWORLD_ZEPHYR_REVISION" ]]; then
    build_die "unexpected Zephyr revision: $revision"
  fi
}
