"""Turn ONNX schema type strings (e.g. "seq(map(string, tensor(float)))") into TypeProto."""

from __future__ import annotations

import onnx
from onnx import TensorProto

ELEM_TYPES = {name.lower(): value for name, value in TensorProto.DataType.items() if name != "UNDEFINED"}


def _split_args(s: str) -> list[str]:
    parts, depth, cur = [], 0, []
    for ch in s:
        if ch == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
            continue
        depth += ch == "("
        depth -= ch == ")"
        cur.append(ch)
    parts.append("".join(cur).strip())
    return parts


def parse_type(type_str: str, shape: list[int] | None = None) -> onnx.TypeProto:
    """Parse a schema type string. `shape` is applied to (sparse) tensor leaves."""
    s = type_str.replace(" ", "")
    tp = onnx.TypeProto()
    if "(" not in s:
        # Bare element types appear as map values, e.g. map(string, int64); ONNX reads them as tensors.
        _set_tensor(tp.tensor_type, s, shape)
        return tp
    ctor, inner = s[: s.index("(")], s[s.index("(") + 1 : -1]
    if ctor == "tensor":
        _set_tensor(tp.tensor_type, inner, shape)
    elif ctor == "sparse_tensor":
        _set_tensor(tp.sparse_tensor_type, inner, shape)
    elif ctor == "seq":
        tp.sequence_type.elem_type.CopyFrom(parse_type(inner, shape))
    elif ctor == "optional":
        tp.optional_type.elem_type.CopyFrom(parse_type(inner, shape))
    elif ctor == "map":
        key, value = _split_args(inner)
        tp.map_type.key_type = ELEM_TYPES[key]
        tp.map_type.value_type.CopyFrom(parse_type(value, shape))
    else:
        raise ValueError(f"unknown type constructor in {type_str!r}")
    return tp


def _set_tensor(t, elem: str, shape: list[int] | None) -> None:
    t.elem_type = ELEM_TYPES[elem]
    if shape is not None:
        t.shape.SetInParent()
        for d in shape:
            t.shape.dim.add().dim_value = d


def preferred(allowed: list[str]) -> str:
    """Pick a representative type: float tensors exercise the most inference code."""
    for want in ("tensor(float)", "tensor(int64)", "tensor(int32)"):
        if want in allowed:
            return want
    return sorted(allowed)[0]
