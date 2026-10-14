# Scope

## Target

[onnx/onnx](https://github.com/onnx/onnx), C++ core, pinned at commit `db5bc99bc777f883d9ea409997fb95e4cb8b5d6a`
(see `ONNX_COMMIT`). Seeds are generated with the released `onnx==1.23.0` Python package, and every finding is
also checked against that release, because it is the version users actually install.

Entry points exercised per input (`harness/target.cc`):

| Stage | API | Why |
|---|---|---|
| Parse | `onnx::ParseProtoFromBytes` | untrusted model bytes |
| Shape inference, default options | `shape_inference::InferShapes(m, registry, {false, 0, false})` | same options as Python `onnx.shape_inference.infer_shapes(model)` |
| Shape inference, strict + data propagation | `InferShapes(m, registry, {true, 0, true})` | reaches the 39 data-propagation functions |
| Checker | `checker::check_model(m, /*full_check=*/true)` | validation of untrusted models |

Operator surface (`docs/scope/schemas.csv`, from `gen/enumerate_schemas.py`):

| Domain | Schema versions | Ops |
|---|---:|---:|
| ai.onnx | 626 | 203 |
| ai.onnx.ml | 23 | 19 |
| ai.onnx.preview | 1 | 1 |
| ai.onnx.preview.training | 4 | 4 |
| **Total (non-deprecated)** | **654** | **227** |

602 of the 654 have a type/shape inference function, and 39 have a data-propagation function.

## What counts as a finding

ONNX's own threat model (`third_party/onnx/docs/AssuranceCase.md`, lines 37–38) defines the boundary:

- **In scope:** "memory safety while parsing, type/shape inference, version conversion, and validation of untrusted
  model bytes". That covers ASan reports (SEGV, heap/stack buffer overflow, use-after-free) and UBSan reports
  (null member call, signed overflow in dimension arithmetic, invalid shifts, out-of-bounds indexing).
- **Out of scope:** "resource exhaustion (DoS) from those utilities". Timeouts, OOMs and
  `allocation-size-too-big` are bucketed `out_of_scope` by `triage/replay.py` and are **never filed**.
- **Needs review:** stack overflow from deep graph nesting, and aborts without a sanitizer report (for example
  `std::terminate`). A human decides on each one.

## Where to report

`third_party/onnx/SECURITY.md`, lines 11–12: "Bugs, even safety-critical ones, that are easily discovered using
widely available tooling are considered publicly known. Please open a public issue or PR if you discovered an issue in
this manner." Sanitizer and fuzzer findings fall under this, so we file them as **public issue + fix PR**, not as
private advisories. Contributions need a DCO sign-off (`git commit -s`) and must pass `lintrunner`.

## Out of scope for this project

- The reference evaluator (`onnx/reference`), which is Python and executes models, and so is excluded by the
  threat model.
- Version converter and model hub. We may add these later if time permits.
- onnxruntime and other downstream consumers.
