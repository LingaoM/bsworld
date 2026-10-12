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
readonly NUTTX_BUILD_USAGE="usage: tests/integration/nuttx/build.sh --nuttx-dir PATH --nuttx-apps-dir PATH --bsim-out-dir PATH [--jobs N] [--skip-nuttx-update]"
# shellcheck source=tests/integration/nuttx/build_common.sh
source "$SCRIPT_DIR/build_common.sh"

nuttx_parse_build_args "$@"
nuttx_prepare_sources

readonly -a child_args=(
  --nuttx-dir "$NUTTX_DIR"
  --nuttx-apps-dir "$NUTTX_APPS_DIR"
  --bsim-out-dir "$BSIM_OUT_DIR"
  --jobs "$BUILD_JOBS"
  --skip-nuttx-update
)

"$SCRIPT_DIR/btsak/build.sh" "${child_args[@]}"
"$SCRIPT_DIR/nimble/build.sh" "${child_args[@]}"
