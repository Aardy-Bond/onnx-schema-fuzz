"""Replay model files through the sanitized driver, one process per file, and bucket crashes.

Each crash is keyed by (sanitizer kind, first ONNX source location in the report),
so many inputs hitting the same bug collapse to one bucket. Buckets are labelled:

  in_scope      memory-safety / UB report (SEGV, heap-*, null member call, ...)
  out_of_scope  resource exhaustion per ONNX's threat model (timeouts, OOM,
                allocation-size-too-big). Never filed upstream.
  review        anything else that killed the process (e.g. stack overflow, abort
                without a sanitizer report); a human decides.

Usage: triage/replay.py seeds/schema [more dirs or files] [-o reports/replay.json]
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import pathlib
import platform
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_DRIVER = ROOT / "build" / f"{platform.system().lower()}-{platform.machine()}" / "harness" / "onnx_driver"
ONNX_SRC = str(ROOT / "third_party" / "onnx") + "/"

ENV = dict(
    os.environ,
    ASAN_OPTIONS="abort_on_error=1:detect_leaks=0:symbolize=1:allocator_may_return_null=0",
    UBSAN_OPTIONS="print_stacktrace=1:halt_on_error=1",
)
OUT_OF_SCOPE_KINDS = {"timeout", "out-of-memory", "allocation-size-too-big", "rss-limit"}
REVIEW_KINDS = {"stack-overflow", "abort-no-report", "signal"}

SUMMARY_RE = re.compile(r"SUMMARY: (\w+Sanitizer): (\S+)")
# Paths may contain spaces (e.g. ".../Software Analysis/..."), so anchor on the line structure.
UBSAN_RE = re.compile(r"^(.+?):(\d+):\d+: runtime error: (.*)$", re.M)
FRAME_RE = re.compile(r"^\s+#\d+ 0x[0-9a-f]+ in (.+) (\S*?\.(?:cc|h|cpp)):(\d+)", re.M)


def onnx_location(log: str) -> str:
    """First stack frame (or UBSan location) inside third_party/onnx, as onnx/...:line."""
    m = UBSAN_RE.search(log)
    if m and ONNX_SRC in m.group(1):
        return f"{m.group(1).replace(ONNX_SRC, '')}:{m.group(2)}"
    for fn, path, line in FRAME_RE.findall(log):
        if ONNX_SRC in path:
            return f"{path.replace(ONNX_SRC, '')}:{line}"
        if path.endswith(".cc") and "/onnx/" in path:
            return f"{path[path.index('onnx/'):]}:{line}"
    # Apple's symbolizer sometimes omits file:line for lambdas; fall back to the function.
    m = re.search(r"^\s+#0 0x[0-9a-f]+ in (.+?) \(", log, re.M)
    return m.group(1)[:160] if m else "unknown"


def classify(rc: int | None, log: str) -> tuple[str, str]:
    if rc is None:
        return "timeout", ""
    m = SUMMARY_RE.search(log)
    if m:
        kind = m.group(2)
        if m.group(1) == "UndefinedBehaviorSanitizer":
            ub = UBSAN_RE.search(log)
            kind = "ub:" + re.sub(r"'[^']*'|\d+", "_", ub.group(3))[:80] if ub else "ub"
        return kind, onnx_location(log)
    if "AddressSanitizer: stack-overflow" in log:
        return "stack-overflow", onnx_location(log)
    if "out of memory" in log or "std::bad_alloc" in log:
        return "out-of-memory", ""
    if rc < 0 or rc >= 128:
        return ("abort-no-report" if rc in (-6, 134) else "signal"), onnx_location(log)
    return "exit-" + str(rc), ""


def run_one(driver: pathlib.Path, path: pathlib.Path, timeout: float) -> dict:
    try:
        p = subprocess.run([str(driver), str(path)], capture_output=True, text=True, timeout=timeout, env=ENV)
        rc, out, err = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        rc, out, err = None, "", ""
    if rc == 0:
        return {"file": str(path), "outcome": out.split("\t", 1)[0] or "unknown"}
    kind, loc = classify(rc, err)
    return {"file": str(path), "outcome": "crash", "kind": kind, "location": loc, "rc": rc, "log": err[-6000:]}


def scope_of(kind: str) -> str:
    if kind in OUT_OF_SCOPE_KINDS:
        return "out_of_scope"
    if kind in REVIEW_KINDS or kind.startswith("exit-"):
        return "review"
    return "in_scope"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", type=pathlib.Path)
    ap.add_argument("--driver", type=pathlib.Path, default=DEFAULT_DRIVER)
    ap.add_argument("--timeout", type=float, default=20.0)
    ap.add_argument("-j", "--jobs", type=int, default=os.cpu_count())
    ap.add_argument("-o", "--out", type=pathlib.Path, default=ROOT / "reports" / "replay.json")
    args = ap.parse_args()

    if not args.driver.exists():
        sys.exit(f"missing driver {args.driver}; run scripts/build_onnx.sh")
    files = sorted(f for p in args.inputs for f in ([p] if p.is_file() else p.rglob("*.onnx")))

    with cf.ThreadPoolExecutor(args.jobs) as ex:
        results = list(ex.map(lambda f: run_one(args.driver, f, args.timeout), files))

    outcomes: dict[str, int] = {}
    buckets: dict[tuple[str, str], dict] = {}
    for r in results:
        outcomes[r["outcome"]] = outcomes.get(r["outcome"], 0) + 1
        if r["outcome"] != "crash":
            continue
        key = (r["kind"], r["location"])
        b = buckets.setdefault(
            key, {"kind": r["kind"], "location": r["location"], "scope": scope_of(r["kind"]), "inputs": [], "log": r["log"]}
        )
        b["inputs"].append(r["file"])

    ordered = sorted(buckets.values(), key=lambda b: (b["scope"], -len(b["inputs"])))
    for b in ordered:
        b["inputs"].sort(key=lambda f: pathlib.Path(f).stat().st_size)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"files": len(files), "outcomes": outcomes, "buckets": ordered}, indent=2))

    print(f"{len(files)} inputs: " + ", ".join(f"{k}={v}" for k, v in sorted(outcomes.items())))
    print(f"{len(ordered)} unique crash buckets:")
    for b in ordered:
        smallest = pathlib.Path(b["inputs"][0]).name
        print(f"  [{b['scope']:12s}] {len(b['inputs']):3d}x  {b['kind'][:60]:60s} {b['location'][:90]}  e.g. {smallest}")
    print(f"details: {args.out}")


if __name__ == "__main__":
    main()
