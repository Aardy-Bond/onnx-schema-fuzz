# Findings ledger

One row per unique bug, keyed by sanitizer kind and ONNX source location (`triage/replay.py`).
States: `candidate` (reproduced locally) → `filed` → `acknowledged` → `fixed (PR merged)`.
Before filing, re-run the duplicate search on issues **and** PRs. The last search (14 Oct 2026) found nothing.

| # | Operator (domain, version) | Defect | Location @ `db5bc99` | Reproducer | Crashes `onnx==1.23.0` | Upstream issue | Fix PR | State |
|---|---|---|---|---|---|---|---|---|
| 1 | DictVectorizer (ai.onnx.ml, 1) | null `TypeProto*` member call: input type not checked | `onnx/defs/traditionalml/defs.cc` (DictVectorizer inference) | `ai.onnx.ml__DictVectorizer__v1__untyped.onnx` | yes (SIGSEGV) | – | – | candidate |
| 2 | LabelEncoder (ai.onnx.ml, 1) | null `TypeProto*` member call | `onnx/defs/traditionalml/old.cc` (LabelEncoder-1 inference) | `ai.onnx.ml__LabelEncoder__v1__untyped.onnx` | yes (SIGSEGV) | – | – | candidate |
| 3 | TreeEnsemble (ai.onnx.ml, 5) | null `TypeProto*` member call | `onnx/defs/traditionalml/defs.cc` (TreeEnsemble-5 inference) | `ai.onnx.ml__TreeEnsemble__v5__untyped.onnx` | yes (SIGSEGV) | – | – | candidate |
| 4 | RegexFullMatch (ai.onnx, 20) | null deref in `propagateShape` via `propagateShapeFromInputToOutput` | `onnx/defs/shape_inference.h:509` | `ai.onnx__RegexFullMatch__v20__untyped.onnx` | yes (SIGSEGV) | – | – | candidate |

UBSan attributes crashes inside inference lambdas to the line where the schema macro ends, so the "location" column
names the operator's inference function instead of an exact line. Pin the exact line in a debugger before writing
the issue.

Reproduce any row:

```bash
.venv/bin/python gen/make_seeds.py && build/darwin-arm64/harness/onnx_driver seeds/schema/<reproducer>
.venv/bin/python -c "import onnx,sys; onnx.shape_inference.infer_shapes(onnx.load(sys.argv[1]))" seeds/schema/<reproducer>
```
