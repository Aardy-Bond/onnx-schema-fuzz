"""Schema-guided seed corpus: one minimal single-node model per (domain, op, since_version).

Variants per schema:
  min      required inputs only, every input fully typed with a rank-2 shape
  full     optional inputs present, variadic inputs repeated twice
  untyped  like `min`, but graph inputs carry no type (exercises the
           unguarded ctx.getInputType(i)-> defect class)

Seeds do not need to be valid models: they only need to parse and reach the
operator's inference function. Coverage-guided mutation takes it from there.
"""

from __future__ import annotations

import argparse
import collections
import pathlib

import onnx
import onnx.defs
import onnx.shape_inference
from onnx import AttributeProto, TensorProto, helper

from schema_types import parse_type, preferred

AttrType = onnx.defs.OpSchema.AttrType
Option = onnx.defs.OpSchema.FormalParameterOption
VARIANTS = ("min", "full", "untyped")
SHAPE = [2, 3]


def default_attribute(name: str, attr_type) -> AttributeProto:
    a = AttributeProto(name=name)
    if attr_type == AttrType.FLOAT:
        a.type, a.f = AttributeProto.FLOAT, 1.0
    elif attr_type == AttrType.INT:
        a.type, a.i = AttributeProto.INT, 1
    elif attr_type == AttrType.STRING:
        a.type, a.s = AttributeProto.STRING, b"a"
    elif attr_type == AttrType.FLOATS:
        a.type = AttributeProto.FLOATS
        a.floats.extend([1.0])
    elif attr_type == AttrType.INTS:
        a.type = AttributeProto.INTS
        a.ints.extend([1])
    elif attr_type == AttrType.STRINGS:
        a.type = AttributeProto.STRINGS
        a.strings.extend([b"a"])
    elif attr_type == AttrType.TENSOR:
        a.type = AttributeProto.TENSOR
        a.t.CopyFrom(helper.make_tensor("t", TensorProto.FLOAT, [1], [1.0]))
    elif attr_type == AttrType.TENSORS:
        a.type = AttributeProto.TENSORS
        a.tensors.add().CopyFrom(helper.make_tensor("t", TensorProto.FLOAT, [1], [1.0]))
    elif attr_type == AttrType.GRAPH:
        a.type = AttributeProto.GRAPH
        a.g.CopyFrom(helper.make_graph([], "body", [], []))
    elif attr_type == AttrType.GRAPHS:
        a.type = AttributeProto.GRAPHS
        a.graphs.add().CopyFrom(helper.make_graph([], "body", [], []))
    elif attr_type == AttrType.TYPE_PROTO:
        a.type = AttributeProto.TYPE_PROTO
        a.tp.CopyFrom(parse_type("tensor(float)", SHAPE))
    elif attr_type == AttrType.TYPE_PROTOS:
        a.type = AttributeProto.TYPE_PROTOS
        a.type_protos.add().CopyFrom(parse_type("tensor(float)", SHAPE))
    elif attr_type == AttrType.SPARSE_TENSOR:
        a.type = AttributeProto.SPARSE_TENSOR
        a.sparse_tensor.dims.extend([1])
    elif attr_type == AttrType.SPARSE_TENSORS:
        a.type = AttributeProto.SPARSE_TENSORS
        a.sparse_tensors.add().dims.extend([1])
    return a


def resolve_type(schema, type_str: str) -> str:
    for tc in schema.type_constraints:
        if tc.type_param_str == type_str:
            return preferred(list(tc.allowed_type_strs))
    return type_str


def input_names(schema, variant: str) -> list[tuple[str, str]]:
    """(graph input name, schema type string) pairs; '' marks a skipped optional slot."""
    out = []
    for i, p in enumerate(schema.inputs):
        if p.option == Option.Optional and variant != "full":
            out.append(("", p.type_str))
        elif p.option == Option.Variadic:
            repeat = 2 if variant == "full" else max(1, p.min_arity)
            out.extend((f"in{i}_{k}", p.type_str) for k in range(repeat))
        else:
            out.append((f"in{i}", p.type_str))
    while out and out[-1][0] == "":
        out.pop()
    return out


def build(schema, variant: str) -> onnx.ModelProto:
    inputs = input_names(schema, variant)
    outputs = [
        f"out{i}"
        for i, p in enumerate(schema.outputs)
        if p.option != Option.Optional or variant == "full" or i == 0
    ]

    node = helper.make_node(schema.name, [n for n, _ in inputs], outputs, domain=schema.domain)
    node.attribute.extend(
        default_attribute(name, a.type) for name, a in sorted(schema.attributes.items()) if a.required
    )

    graph_inputs = []
    for name, type_str in inputs:
        if not name:
            continue
        vi = onnx.ValueInfoProto(name=name)
        if variant != "untyped":
            vi.type.CopyFrom(parse_type(resolve_type(schema, type_str), SHAPE))
        graph_inputs.append(vi)

    graph = helper.make_graph(
        [node],
        f"{schema.name}_v{schema.since_version}_{variant}",
        graph_inputs,
        [onnx.ValueInfoProto(name=n) for n in outputs],
    )
    opsets = [helper.make_opsetid(schema.domain, schema.since_version)]
    if schema.domain != "":
        opsets.append(helper.make_opsetid("", 21))
    model = helper.make_model(graph, opset_imports=opsets)
    if variant != "untyped":
        fill_output_types(model)
    return model


def fill_output_types(model: onnx.ModelProto) -> None:
    """Copy inferred types onto graph outputs so the checker gets past its value_info checks."""
    try:
        inferred = onnx.shape_inference.infer_shapes(model)
    except Exception:  # noqa: BLE001 - seed stays usable for inference even if this fails
        return
    known = {vi.name: vi.type for vi in list(inferred.graph.value_info) + list(inferred.graph.output)}
    for out in model.graph.output:
        if out.name in known and known[out.name].WhichOneof("value") is not None:
            out.type.CopyFrom(known[out.name])


def seed_name(schema, variant: str) -> str:
    domain = schema.domain or "ai.onnx"
    return f"{domain}__{schema.name}__v{schema.since_version}__{variant}.onnx"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--out", default="seeds/schema")
    ap.add_argument("--variants", default=",".join(VARIANTS))
    ap.add_argument("--include-deprecated", action="store_true")
    args = ap.parse_args()

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    variants = [v for v in args.variants.split(",") if v]
    stats, failed = collections.Counter(), []

    for schema in onnx.defs.get_all_schemas_with_history():
        if schema.deprecated and not args.include_deprecated:
            continue
        for variant in variants:
            try:
                data = build(schema, variant).SerializeToString()
            except Exception as e:  # noqa: BLE001 - report and keep generating
                failed.append(f"{seed_name(schema, variant)}: {e}")
                continue
            (out / seed_name(schema, variant)).write_bytes(data)
            stats[variant] += 1

    print(f"wrote {sum(stats.values())} seeds to {out}: " + ", ".join(f"{v}={n}" for v, n in stats.items()))
    for line in failed:
        print("  skipped", line)


if __name__ == "__main__":
    main()
