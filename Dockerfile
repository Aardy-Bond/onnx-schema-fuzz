# Linux image with LLVM clang + libFuzzer. The repo is bind-mounted at /work, so
# build outputs land in build/linux-<arch>/ next to the native macOS build.
#
#   docker build -t onnx-schema-fuzz .
#   docker run --rm -it -v "$PWD":/work onnx-schema-fuzz            # FUZZ=1 build + smoke test
#   docker run --rm -it -v "$PWD":/work onnx-schema-fuzz bash       # shell
FROM ubuntu:24.04

ARG LLVM=18
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      clang-${LLVM} llvm-${LLVM} libclang-rt-${LLVM}-dev lld-${LLVM} \
      cmake ninja-build git ca-certificates python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*

ENV CC=clang-${LLVM} CXX=clang++-${LLVM} \
    ASAN_SYMBOLIZER_PATH=/usr/bin/llvm-symbolizer-${LLVM} \
    PY=/opt/venv/bin/python

COPY requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt

RUN git config --global --add safe.directory '*'
WORKDIR /work
CMD ["bash", "-c", "FUZZ=1 scripts/build_onnx.sh && scripts/smoke_test.sh"]
