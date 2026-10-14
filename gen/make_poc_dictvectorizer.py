"""Known-crash smoke-test input: ai.onnx.ml DictVectorizer whose input has no type.

DictVectorizer's inference function dereferences ctx.getInputType(0) without a
null check, so shape inference on this model segfaults. This is the pipeline's
positive control: if the sanitized driver does not report it, the build is broken.
"""

import argparse
import pathlib

import onnx
from onnx import helper


def build() -> onnx.ModelProto:
    node = helper.make_node(
        "DictVectorizer", ["a"], ["b"], domain="ai.onnx.ml", int64_vocabulary=[1, 2, 3]
    )
    untyped_input = onnx.ValueInfoProto(name="a")
    graph = helper.make_graph(
        [node], "dv_untyped", [untyped_input], [helper.make_empty_tensor_value_info("b")]
    )
    return helper.make_model(
        graph,
        opset_imports=[helper.make_opsetid("", 17), helper.make_opsetid("ai.onnx.ml", 1)],
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="seeds/poc/dictvectorizer_untyped.onnx")
    args = ap.parse_args()
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    data = build().SerializeToString()
    out.write_bytes(data)
    print(f"wrote {out} ({len(data)} bytes)")


if __name__ == "__main__":
    main()
