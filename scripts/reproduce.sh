#!/usr/bin/env bash
# One-command reproduction: build, smoke test, generate the seed corpus, replay it, triage.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

PY="${PY:-${ROOT}/.venv/bin/python}"
if [[ ! -x "${PY}" ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
  PY="${ROOT}/.venv/bin/python"
fi
export PY

scripts/build_onnx.sh
scripts/smoke_test.sh
"${PY}" gen/enumerate_schemas.py
"${PY}" gen/make_seeds.py -o seeds/schema
"${PY}" triage/replay.py seeds/schema
"${PY}" triage/census_getinputtype.py | tail -1
