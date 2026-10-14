# Progress Meeting 1 (11–16 Oct)

PM1 asks for three things: scope firmed up, target accessible, and an initial pipeline running. All three are done,
and the pipeline has already produced four crash candidates.

## 1. Scope (see SCOPE.md)

- Target: the onnx/onnx C++ core at commit `db5bc99`. Entry points: `ParseProtoFromBytes`, `InferShapes` (with
  default options and with strict + data-propagation options), and `check_model(full_check)`.
- Surface: 654 non-deprecated schema versions, 227 ops, 602 inference functions, 39 data-propagation functions.
- Findings: memory safety and UB only, per ONNX's threat model (`docs/AssuranceCase.md`, lines 37–38).
  Resource exhaustion is filtered out automatically and never filed.
- Reporting: public issue + fix PR, per `SECURITY.md` lines 11–12 (bugs found with common tooling count as public).

## 2. Target accessible

- ONNX builds from source with ASan and UBSan in about 75 seconds on an M-series Mac (`scripts/build_onnx.sh`).
- Positive control (`scripts/smoke_test.sh`): a valid model is accepted cleanly, and the DictVectorizer PoC is caught
  by UBSan as `member call on null pointer of type 'onnx::TypeProto'`.

## 3. Pipeline running end to end

```
schema registry ──► gen/make_seeds.py ──► 1962 seeds ──► onnx_driver (ASan+UBSan) ──► triage/replay.py
 (654 versions)      min / full / untyped                 parse → infer ×2 → check       dedup + scope filter
```

First replay of the seed corpus (about 80 seconds, 10 cores):

| Outcome | Count |
|---|---:|
| accepted by checker | 813 |
| rejected (exception) | 1145 |
| crash | 4 → **4 unique buckets, all in scope** |

| Bucket | Location | Also crashes released `onnx==1.23.0`? |
|---|---|---|
| DictVectorizer-1, null `TypeProto*` | `traditionalml/defs.cc` | yes, SIGSEGV |
| LabelEncoder-1, null `TypeProto*` | `traditionalml/old.cc` | yes, SIGSEGV |
| TreeEnsemble-5, null `TypeProto*` | `traditionalml/defs.cc` | yes, SIGSEGV |
| RegexFullMatch-20, null deref in `propagateShape` | `shape_inference.h:509` | yes, SIGSEGV |

No existing upstream issue or PR found as of 14 Oct. The static census finds 221 `getInputType(N)->` dereference
sites and 13 inference functions with no visible guard (7 of them in `tensor/old.cc`). Most of the 13 did not crash in
replay, and working out why (an earlier check fails first, or the seed never reaches them) is the next lead.

## Demo script (about 5 minutes)

```bash
scripts/smoke_test.sh
.venv/bin/python triage/replay.py seeds/schema
.venv/bin/python -c "import onnx,sys; onnx.shape_inference.infer_shapes(onnx.load(sys.argv[1]))" \
    seeds/schema/ai.onnx__RegexFullMatch__v20__untyped.onnx; echo "exit=$?"     # 139 = SIGSEGV
```

## Next steps (to PM2, 26–30 Oct)

| Owner | Task |
|---|---|
| A | libFuzzer target running in Docker; libprotobuf-mutator over `ModelProto`; OSS-Fuzz build.sh fix |
| B | Targeted mutators (desync weight/input rank, INT64 boundary dims, constant initializers for shape inputs) |
| C | Explain the census-flagged functions that did not crash; exact-line triage; evaluation plan (coverage vs Atheris) |
| C + all | File the first issues and PRs right after PM1 (not on 26–28 Oct as originally planned), because the candidates exist now and maintainers need time to merge |

## Questions for the professor

1. Does an upstream issue that the maintainers fix themselves count, or must the merged PR be ours?
2. Several of the bugs share one root cause (`propagateShapeFromInputToOutput` does not null-check). Does one PR
   fixing the shared helper count as one bug or several?

## Risks

- The defect class is known (issue #2647, 2020) and maintainers may batch-fix it. Mitigation: file quickly, then move
  on to rank/overflow mutators that reach different defect classes.
- Docker Desktop is not running on the dev machine yet, so the libFuzzer build is untested. The Dockerfile is ready.
