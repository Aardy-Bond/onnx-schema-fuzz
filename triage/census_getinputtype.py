"""Static census of the null-dereference defect class in ONNX operator definitions.

Counts, per file under onnx/defs, direct dereferences `ctx.getInputType(N)->...`
and how many of them sit in an inference function with no visible guard
(hasInputShape / hasNInputShapes / null check on getInputType). This is a
heuristic hunting guide, not a proof: guards in helpers are not followed.
"""

import argparse
import collections
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEREF = re.compile(r"getInputType\(\s*(\w+)\s*\)\s*->")
GUARD = re.compile(r"hasInputShape|hasNInputShapes|getInputType\(\s*\w+\s*\)\s*(==|!=)\s*nullptr|if\s*\(\s*!?\s*ctx\.getInputType")


def lambda_bodies(text: str):
    """Yield (start_line, body) for each TypeAndShapeInferenceFunction lambda."""
    for m in re.finditer(r"TypeAndShapeInferenceFunction\(\s*\[[^\]]*\]\s*\([^)]*\)\s*\{", text):
        depth, i = 1, m.end()
        while depth and i < len(text):
            depth += text[i] == "{"
            depth -= text[i] == "}"
            i += 1
        yield text.count("\n", 0, m.start()) + 1, text[m.end() : i]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=pathlib.Path, default=ROOT / "third_party" / "onnx")
    args = ap.parse_args()

    totals = collections.Counter()
    rows = []
    for path in sorted((args.src / "onnx" / "defs").rglob("*.cc")):
        text = path.read_text(errors="replace")
        derefs = len(DEREF.findall(text))
        unguarded = []
        for line, body in lambda_bodies(text):
            if DEREF.search(body) and not GUARD.search(body):
                unguarded.append(line)
        if derefs:
            rows.append((str(path.relative_to(args.src)), derefs, unguarded))
            totals["derefs"] += derefs
            totals["unguarded"] += len(unguarded)

    for rel, derefs, unguarded in sorted(rows, key=lambda r: -len(r[2])):
        lines = ",".join(map(str, unguarded[:12])) + ("..." if len(unguarded) > 12 else "")
        print(f"{rel:48s} derefs={derefs:3d} unguarded_fns={len(unguarded):3d} {lines}")
    print(f"total: {totals['derefs']} getInputType(N)-> sites, {totals['unguarded']} inference functions with no visible guard")


if __name__ == "__main__":
    main()
