# onnx-schema-fuzz

Schema-guided, sanitizer-instrumented fuzzing of ONNX's C++ type/shape inference and model checker.
CS 5187 term project.

ONNX's OSS-Fuzz build unsets `CFLAGS`/`CXXFLAGS`, so the C++ core it fuzzes runs **without** sanitizer or coverage
instrumentation. This project builds the core with ASan and UBSan. It generates one model per operator schema
version (654 of them) and replays and fuzzes those models through the same entry points users call:
`infer_shapes` and `check_model`. See [docs/SCOPE.md](docs/SCOPE.md) for what counts as a finding.

## Upstream reports

| # | Bug | Issue | PR | State |
|---|---|---|---|---|
| 1 | DictVectorizer-1 null deref in shape inference (untyped input) | – | – | candidate, not yet filed |
| 2 | LabelEncoder-1 null deref in shape inference | – | – | candidate, not yet filed |
| 3 | TreeEnsemble-5 null deref in shape inference | – | – | candidate, not yet filed |
| 4 | RegexFullMatch-20 null deref via `propagateShapeFromInputToOutput` | – | – | candidate, not yet filed |

Full ledger: [reports/README.md](reports/README.md).

## Reproduce everything (one command)

```bash
git clone https://github.com/Aardy-Bond/onnx-schema-fuzz.git && cd onnx-schema-fuzz
scripts/reproduce.sh
```

This clones ONNX at the pinned commit, builds it with ASan and UBSan, runs the smoke test, generates the seed
corpus, replays the corpus, and prints the deduplicated crash buckets. On an M-series Mac it takes about 3 minutes
the first time and about 90 seconds after that.

### Individual steps

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
scripts/build_onnx.sh                       # ONNX + harness -> build/<os>-<arch>/harness/onnx_driver
scripts/smoke_test.sh                       # valid model accepted, DictVectorizer PoC crashes under UBSan
.venv/bin/python gen/enumerate_schemas.py   # scope inventory -> docs/scope/schemas.csv
.venv/bin/python gen/make_seeds.py          # 1962 seeds -> seeds/schema/
.venv/bin/python triage/replay.py seeds/schema   # dedup crashes -> reports/replay.json
.venv/bin/python triage/census_getinputtype.py   # static census of getInputType(N)-> sites
OSF_VERBOSE=1 build/*/harness/onnx_driver model.onnx   # print why a model is rejected
```

### libFuzzer (Linux / Docker)

Apple clang has no libFuzzer, so on macOS the native build produces only the replay driver. The fuzzer is built
in Docker:

```bash
docker build -t onnx-schema-fuzz .
docker run --rm -it -v "$PWD":/work onnx-schema-fuzz        # FUZZ=1 build + smoke test
docker run --rm -it -v "$PWD":/work onnx-schema-fuzz bash -c \
  'build/linux-*/harness/fuzz_shape_inference -max_total_time=600 -rss_limit_mb=2048 corpus/ seeds/schema/'
```

## Exact dependencies

| Component | Version |
|---|---|
| ONNX (C++ target) | commit `db5bc99bc777f883d9ea409997fb95e4cb8b5d6a` (`ONNX_COMMIT`) |
| ONNX (Python, seed generation and release check) | `onnx==1.23.0`, `protobuf==7.36.2` (`requirements.txt`) |
| Python | 3.12 |
| macOS build | macOS 26.5, Apple clang 21.0.0, CMake 4.1.2, Ninja 1.13.1, Homebrew protobuf 34.1, abseil 20260107.1 |
| Linux build | Ubuntu 24.04, clang/LLVM 18 with libFuzzer, protobuf built by ONNX (`ONNX_BUILD_CUSTOM_PROTOBUF=ON`) |

## Layout

```
harness/   target.cc (parse -> infer_shapes x2 -> check_model), driver.cc (replay), fuzz_shape_inference.cc (libFuzzer)
gen/       schema enumeration, schema-guided seed generator, known-crash PoC
triage/    replay + crash dedup/scope filter, static getInputType census
scripts/   build_onnx.sh, smoke_test.sh, reproduce.sh
docs/      SCOPE.md, PM1.md, scope/schemas.csv
reports/   findings ledger
```

## License

Apache-2.0 (same as ONNX). See [LICENSE](LICENSE).
