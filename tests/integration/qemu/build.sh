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
readonly ROOT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
readonly QEMU_REPOSITORY="https://github.com/LingaoM/qemu.git"
readonly QEMU_REVISION="b2d1776bca209773c4a023e4decb785f7dc3cfb4"
readonly BUILDROOT_REPOSITORY="https://gitlab.com/buildroot.org/buildroot.git"
readonly BUILDROOT_REVISION="1ad0796f2b40eb8dadc43e95dd1d56708b191375"
readonly GUEST_SOURCE_DIR="$SCRIPT_DIR/source"
readonly PREBUILT_DIR="$SCRIPT_DIR/prebuilt"
# shellcheck source=scripts/build_helpers.sh
source "$ROOT_DIR/scripts/build_helpers.sh"

usage() {
  cat <<'EOF'
usage: tests/integration/qemu/build.sh \
  --qemu-dir PATH \
  --buildroot-dir PATH \
  --bsim-out-dir PATH \
  [--qemu-build-dir PATH] \
  [--buildroot-output-dir PATH] \
  [--jobs N] \
  [--skip-source-update]
EOF
}

prepare_checkout() {
  local name="$1"
  local directory="$2"
  local repository="$3"
  local revision="$4"
  local actual_revision

  git -C "$directory" rev-parse --is-inside-work-tree >/dev/null 2>&1 ||
    build_die "$name directory is not a Git checkout: $directory"

  if [[ "$skip_source_update" != yes ]]; then
    if ! git -C "$directory" diff --quiet ||
      ! git -C "$directory" diff --cached --quiet; then
      build_die "$name checkout has uncommitted tracked changes: $directory"
    fi

    echo "==> Preparing $name $revision"
    git -C "$directory" fetch --prune "$repository"
    git -C "$directory" fetch "$repository" "$revision"
    git -C "$directory" checkout --detach "$revision"
  fi

  actual_revision="$(git -C "$directory" rev-parse HEAD)"
  if [[ "$actual_revision" != "$revision" ]]; then
    build_die "unexpected $name revision: $actual_revision"
  fi
}

qemu_dir=""
buildroot_dir=""
bsim_out_dir=""
qemu_build_dir=""
buildroot_output_dir=""
build_jobs="$(nproc)"
skip_source_update=no

while [[ $# -gt 0 ]]; do
  case "$1" in
    --qemu-dir) qemu_dir="${2:-}"; shift 2 ;;
    --buildroot-dir) buildroot_dir="${2:-}"; shift 2 ;;
    --bsim-out-dir) bsim_out_dir="${2:-}"; shift 2 ;;
    --qemu-build-dir) qemu_build_dir="${2:-}"; shift 2 ;;
    --buildroot-output-dir) buildroot_output_dir="${2:-}"; shift 2 ;;
    --jobs) build_jobs="${2:-}"; shift 2 ;;
    --skip-source-update) skip_source_update=yes; shift ;;
    -h | --help) usage; exit 0 ;;
    *) build_die "unknown argument: $1" ;;
  esac
done

[[ -n "$qemu_dir" ]] || build_die "--qemu-dir is required"
[[ -n "$buildroot_dir" ]] || build_die "--buildroot-dir is required"
[[ -n "$bsim_out_dir" ]] || build_die "--bsim-out-dir is required"
[[ "$build_jobs" =~ ^[1-9][0-9]*$ ]] || build_die "--jobs must be a positive integer"

build_require_directory "QEMU" "$qemu_dir"
build_require_directory "Buildroot" "$buildroot_dir"
build_require_directory "BabbleSim output" "$bsim_out_dir"
build_require_directory "BabbleSim components" "$ROOT_DIR/components/babblesim/components"
build_require_command git
build_require_command install
build_require_command make
build_require_command ninja
build_require_command realpath

qemu_dir="$(realpath "$qemu_dir")"
buildroot_dir="$(realpath "$buildroot_dir")"
bsim_out_dir="$(realpath "$bsim_out_dir")"
bsim_components_dir="$(realpath "$ROOT_DIR/components/babblesim/components")"
qemu_build_dir="${qemu_build_dir:-$qemu_dir/build/bsworld}"
buildroot_output_dir="${buildroot_output_dir:-$buildroot_dir/output-bsworld-linux}"
mkdir -p "$qemu_build_dir" "$buildroot_output_dir"
qemu_build_dir="$(realpath "$qemu_build_dir")"
buildroot_output_dir="$(realpath "$buildroot_output_dir")"

[[ -f "$bsim_out_dir/lib/libPhyComv1.a" ]] ||
  build_die "BabbleSim libraries not found under: $bsim_out_dir/lib"

prepare_checkout QEMU "$qemu_dir" "$QEMU_REPOSITORY" "$QEMU_REVISION"
prepare_checkout Buildroot "$buildroot_dir" "$BUILDROOT_REPOSITORY" "$BUILDROOT_REVISION"

echo "==> Building QEMU"
(
  cd "$qemu_build_dir"
  "$qemu_dir/configure" \
    --target-list=aarch64-softmmu \
    --enable-bsim \
    --bsim-components-path="$bsim_components_dir" \
    --bsim-out-path="$bsim_out_dir"
)
ninja -C "$qemu_build_dir" qemu-system-aarch64

echo "==> Building Linux Guest"
make -C "$buildroot_dir" \
  O="$buildroot_output_dir" \
  BR2_EXTERNAL="$GUEST_SOURCE_DIR" \
  bsworld_qemu_linux_defconfig
make -C "$buildroot_dir" O="$buildroot_output_dir" -j"$build_jobs"

qemu_binary="$qemu_build_dir/qemu-system-aarch64"
kernel_image="$buildroot_output_dir/images/Image"
rootfs_image="$buildroot_output_dir/images/rootfs.cpio"
build_require_executable "QEMU" "$qemu_binary"
[[ -f "$kernel_image" ]] || build_die "Linux kernel not found: $kernel_image"
[[ -f "$rootfs_image" ]] || build_die "Guest root filesystem not found: $rootfs_image"

staging_dir="$PREBUILT_DIR.tmp.$$"
cleanup() {
  rm -rf "$staging_dir"
}
trap cleanup EXIT

rm -rf "$staging_dir"
mkdir -p "$staging_dir"
install -m 0755 "$qemu_binary" "$staging_dir/qemu-system-aarch64"
install -m 0644 "$kernel_image" "$staging_dir/Image"
install -m 0644 "$rootfs_image" "$staging_dir/rootfs.cpio"
rm -rf "$PREBUILT_DIR"
mv "$staging_dir" "$PREBUILT_DIR"
trap - EXIT

echo "Built QEMU Linux test runtime in $PREBUILT_DIR"
