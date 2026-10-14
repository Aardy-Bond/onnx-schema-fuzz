"""Scope inventory: every operator schema version the fuzzer targets.

Writes one CSV row per (domain, op, since_version) and prints per-domain totals.
"""

import argparse
import collections
import csv
import pathlib

import onnx
import onnx.defs

Option = onnx.defs.OpSchema.FormalParameterOption


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="docs/scope/schemas.csv")
    args = ap.parse_args()
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for s in onnx.defs.get_all_schemas_with_history():
        rows.append(
            {
                "domain": s.domain or "ai.onnx",
                "op": s.name,
                "since_version": s.since_version,
                "deprecated": int(s.deprecated),
                "has_inference_fn": int(s.has_type_and_shape_inference_function),
                "has_data_propagation_fn": int(s.has_data_propagation_function),
                "has_function_body": int(s.has_function or s.has_context_dependent_function),
                "inputs": len(s.inputs),
                "optional_inputs": sum(p.option == Option.Optional for p in s.inputs),
                "variadic_inputs": sum(p.option == Option.Variadic for p in s.inputs),
                "attributes": len(s.attributes),
                "required_attributes": sum(a.required for a in s.attributes.values()),
                "source": f"{s.file}:{s.line}",
            }
        )
    rows.sort(key=lambda r: (r["domain"], r["op"], r["since_version"]))
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    live = [r for r in rows if not r["deprecated"]]
    by_domain = collections.Counter(r["domain"] for r in live)
    ops = {(r["domain"], r["op"]) for r in live}
    print(f"onnx {onnx.__version__}: {len(rows)} schema versions ({len(live)} non-deprecated), {len(ops)} distinct ops")
    for domain, n in sorted(by_domain.items()):
        n_ops = len({op for d, op in ops if d == domain})
        print(f"  {domain:28s} {n:4d} versions  {n_ops:4d} ops")
    print(f"  with inference function:   {sum(r['has_inference_fn'] for r in live)}")
    print(f"  with data propagation:     {sum(r['has_data_propagation_fn'] for r in live)}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
