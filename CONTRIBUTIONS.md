# Contribution statement

Each member fills in their own section, signs it, and commits it **from their own account**, so the commit history
backs up the statement. Every member must be able to explain every part of the project.

## Member A: build, harness, OSS-Fuzz (name: ____________)

- Sanitized ONNX build (`scripts/build_onnx.sh`, `Dockerfile`)
- Harness and libFuzzer target (`harness/`), libprotobuf-mutator integration
- OSS-Fuzz `projects/onnx/build.sh` instrumentation fix (upstream PR: ____)
- Upstream PRs authored: ____

Signature / date: ____________

## Member B: input generation and mutators (name: ____________)

- Schema-guided seed corpus (`gen/make_seeds.py`, `gen/schema_types.py`)
- Targeted mutators: strip type info, desynchronize ranks, boundary dimensions
- Upstream PRs authored: ____

Signature / date: ____________

## Member C: triage, evaluation, upstream, paper lead (name: ____________)

- Triage and dedup (`triage/replay.py`), static census (`triage/census_getinputtype.py`)
- Evaluation (coverage versus Atheris baseline, time to first crash), findings ledger (`reports/README.md`)
- Upstream issues filed: ____; paper sections led: ____

Signature / date: ____________
