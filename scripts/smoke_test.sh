#!/usr/bin/env bash
# Positive control for the sanitizer pipeline: the DictVectorizer PoC must crash
# the sanitized driver with a sanitizer report, and a valid model must not.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLATFORM="$(uname -s | tr '[:upper:]' '[:lower:]')-$(uname -m)"
DRIVER="${DRIVER:-${ROOT}/build/${PLATFORM}/harness/onnx_driver}"
PY="${PY:-${ROOT}/.venv/bin/python}"
OUT="${ROOT}/logs/smoke"
mkdir -p "${OUT}"

export ASAN_OPTIONS="${ASAN_OPTIONS:-abort_on_error=1:detect_leaks=0:symbolize=1}"
export UBSAN_OPTIONS="${UBSAN_OPTIONS:-print_stacktrace=1:halt_on_error=1}"

[[ -x "${DRIVER}" ]] || { echo "missing ${DRIVER}; run scripts/build_onnx.sh"; exit 2; }

"${PY}" "${ROOT}/gen/make_poc_dictvectorizer.py" -o "${OUT}/dictvectorizer_untyped.onnx"
"${PY}" - "${OUT}/valid_relu.onnx" <<'EOF'
import sys
from onnx import TensorProto, helper
g = helper.make_graph(
    [helper.make_node("Relu", ["x"], ["y"])], "relu",
    [helper.make_tensor_value_info("x", TensorProto.FLOAT, [2, 3])],
    [helper.make_tensor_value_info("y", TensorProto.FLOAT, [2, 3])])
open(sys.argv[1], "wb").write(helper.make_model(g, opset_imports=[helper.make_opsetid("", 17)]).SerializeToString())
EOF

fail=0

"${DRIVER}" "${OUT}/valid_relu.onnx" > "${OUT}/valid.log" 2>&1
if [[ $? -eq 0 ]] && grep -q '^accepted' "${OUT}/valid.log"; then
  echo "PASS  valid Relu model accepted without sanitizer reports"
else
  echo "FAIL  valid Relu model:"; cat "${OUT}/valid.log"; fail=1
fi

"${DRIVER}" "${OUT}/dictvectorizer_untyped.onnx" > "${OUT}/poc.log" 2>&1
rc=$?
if [[ ${rc} -ne 0 ]] && grep -qE 'ERROR: (AddressSanitizer|UndefinedBehaviorSanitizer)|runtime error:' "${OUT}/poc.log"; then
  echo "PASS  DictVectorizer PoC crashes the driver (exit ${rc}):"
  grep -E 'SUMMARY:|runtime error:' "${OUT}/poc.log" | head -3 | sed 's/^/        /'
  grep -E '^ +#[0-9]+ ' "${OUT}/poc.log" | head -4 | sed 's/^/        /'
else
  echo "FAIL  DictVectorizer PoC did not produce a sanitizer report (exit ${rc}):"; tail -20 "${OUT}/poc.log"; fail=1
fi

echo "full logs: ${OUT}/"
exit ${fail}
