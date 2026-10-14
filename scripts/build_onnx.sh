#!/usr/bin/env bash
# Build ONNX's C++ core (libonnx + libonnx_proto) with AddressSanitizer and
# UndefinedBehaviorSanitizer, then the harness binaries in harness/.
#
# Usage:
#   scripts/build_onnx.sh            # sanitizer build, driver only
#   FUZZ=1 scripts/build_onnx.sh     # also add -fsanitize=fuzzer-no-link and build the libFuzzer target
#                                    # (needs an LLVM clang with libFuzzer, i.e. the Docker image)
#
# Output goes to build/<platform>/ so a native macOS build and a Docker build never collide.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ONNX_SRC="${ROOT}/third_party/onnx"
ONNX_COMMIT="$(tr -d '[:space:]' < "${ROOT}/ONNX_COMMIT")"
PLATFORM="$(uname -s | tr '[:upper:]' '[:lower:]')-$(uname -m)"
BUILD="${ROOT}/build/${PLATFORM}"
PREFIX="${BUILD}/prefix"
JOBS="${JOBS:-$( (nproc 2>/dev/null || sysctl -n hw.ncpu) )}"
FUZZ="${FUZZ:-0}"

if [[ ! -d "${ONNX_SRC}/.git" ]]; then
  git clone https://github.com/onnx/onnx.git "${ONNX_SRC}"
fi
git -C "${ONNX_SRC}" fetch --quiet --depth 1 origin "${ONNX_COMMIT}" 2>/dev/null || true
git -C "${ONNX_SRC}" checkout --quiet "${ONNX_COMMIT}"
echo "[build] onnx @ $(git -C "${ONNX_SRC}" rev-parse --short HEAD), platform ${PLATFORM}, fuzz=${FUZZ}"

export CC="${CC:-clang}"
export CXX="${CXX:-clang++}"
if [[ "$(uname -s)" == "Darwin" ]]; then
  # Anaconda ships its own clang/protobuf that CMake otherwise picks up first.
  export CC=/usr/bin/clang CXX=/usr/bin/clang++
  EXTRA_CMAKE=(-DCMAKE_PREFIX_PATH=/opt/homebrew -DCMAKE_IGNORE_PREFIX_PATH=/opt/anaconda3)
else
  # Linux image: let ONNX build the protobuf version it pins.
  EXTRA_CMAKE=(-DONNX_BUILD_CUSTOM_PROTOBUF=ON)
fi

SAN_FLAGS="-fsanitize=address,undefined -fno-omit-frame-pointer -fno-sanitize-recover=undefined"
if [[ "${FUZZ}" == "1" ]]; then
  SAN_FLAGS="${SAN_FLAGS} -fsanitize=fuzzer-no-link"
fi

GEN=()
command -v ninja >/dev/null && GEN=(-G Ninja)

cmake -S "${ONNX_SRC}" -B "${BUILD}/onnx" "${GEN[@]}" \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DCMAKE_INSTALL_PREFIX="${PREFIX}" \
  -DCMAKE_C_FLAGS="${SAN_FLAGS}" \
  -DCMAKE_CXX_FLAGS="${SAN_FLAGS}" \
  -DONNX_USE_ASAN=ON \
  -DONNX_ML=ON \
  -DONNX_BUILD_TESTS=OFF \
  -DONNX_BUILD_PYTHON=OFF \
  -DONNX_USE_PROTOBUF_SHARED_LIBS=OFF \
  "${EXTRA_CMAKE[@]}"
cmake --build "${BUILD}/onnx" -j "${JOBS}"
cmake --install "${BUILD}/onnx" >/dev/null

cmake -S "${ROOT}/harness" -B "${BUILD}/harness" "${GEN[@]}" \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DCMAKE_PREFIX_PATH="${PREFIX};/opt/homebrew" \
  -DCMAKE_IGNORE_PREFIX_PATH=/opt/anaconda3 \
  -DSAN_FLAGS="${SAN_FLAGS}" \
  -DBUILD_LIBFUZZER="${FUZZ}"
cmake --build "${BUILD}/harness" -j "${JOBS}"

echo "[build] done: ${BUILD}/harness/"
ls "${BUILD}/harness" | grep -E '^(onnx_driver|fuzz_shape_inference)$' || true
