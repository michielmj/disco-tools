"""
label_selector.core
-------------------

Internal utilities for the Label Selector engine.

This module provides:
- JSON/YAML primitive validation (`validate_primitive`, `validate_primitive_list`)
- rule structure normalization (`normalize`)
- and compilation of normalized rule trees into fast predicate callables (`compile_node`).

Design notes:
- Only JSON/YAML primitive types (None, bool, int, float, str) are accepted as values.
- `compile_node()` builds short-circuiting lambdas optimized for millions of evaluations/sec.
- This module is internal — users should import through `label_selector`'s public API instead.

Example (internal use):
    >>> from label_selector.core import normalize, compile_node
    >>> rule = {"match": {"key": "env", "op": "eq", "value": "prod"}}
    >>> pred = compile_node(normalize(rule))
    >>> pred({"env": "prod"})
    True
"""
from typing import Any, Callable, Dict, Iterable, List, Union

Json = Dict[str, Any]
Primitive = Union[None, bool, int, float, str]
_MISSING = object()

__all__ = [
    "Json",
    "Primitive",
    "_MISSING",
    "validate_primitive",
    "validate_primitive_list",
    "normalize",
    "compile_node",
]


# ---------- Validation helpers ----------

def validate_primitive(value: Any, context: str = "value") -> Primitive:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"{context} must be a JSON primitive (str, int, float, bool, None), not {type(value).__name__}")


def validate_primitive_list(values: Iterable[Any], context: str = "values") -> List[Primitive]:
    return [validate_primitive(v, f"{context} element") for v in values]


# ---------- Normalization ----------

def normalize(node: Json) -> Json:
    if "all" in node:
        return {"all": [normalize(n) for n in node["all"]]}
    if "any" in node:
        return {"any": [normalize(n) for n in node["any"]]}
    if "not" in node:
        return {"not": normalize(node["not"])}
    if "match" in node:
        m = node["match"]
        op_ = m["op"].lower()
        k = m["key"]
        if op_ == "exists":
            return {"match": {"key": k, "op": "exists"}}
        if op_ in {"eq", "ne", "gt", "gte", "lt", "lte"}:
            validate_primitive(m["value"], "match.value")
            return {"match": {"key": k, "op": op_, "value": m["value"]}}
        if op_ in {"in", "notin"}:
            validate_primitive_list(m["values"], "match.values")
            return {"match": {"key": k, "op": op_, "values": list(m["values"])}}
        if op_ in {"between", "notbetween"}:
            r = m["range"]
            inc = r.get("inclusive", {"low": True, "high": True})
            if isinstance(inc, bool):
                inc = {"low": inc, "high": inc}
            # low/high may be None
            if r.get("low") is not None:
                validate_primitive(r["low"], "range.low")
            if r.get("high") is not None:
                validate_primitive(r["high"], "range.high")
            return {
                "match": {
                    "key": k,
                    "op": op_,
                    "range": {"low": r.get("low"), "high": r.get("high"), "inclusive": inc},
                }
            }
    raise ValueError("Invalid rule")


# ---------- Compiler (fast, short-circuit) ----------

def compile_node(node: Json) -> Callable[[Dict[str, Any]], bool]:
    if "all" in node:
        preds = [compile_node(n) for n in node["all"]]

        def _all(meta):
            for p in preds:
                if not p(meta): return False
            return True

        return _all
    if "any" in node:
        preds = [compile_node(n) for n in node["any"]]

        def _any(meta):
            for p in preds:
                if p(meta): return True
            return False

        return _any
    if "not" in node:
        pred = compile_node(node["not"])
        return lambda meta: not pred(meta)
    if "match" in node:
        m = node["match"]
        key = m["key"]
        op_ = m["op"]

        def _get(meta):
            return meta.get(key, _MISSING)

        if op_ == "exists": return lambda meta: key in meta
        if op_ == "eq":
            v = m["value"]
            return lambda meta: _get(meta) == v
        if op_ == "ne":
            v = m["value"]
            return lambda meta: _get(meta) != v
        if op_ == "gt":
            v = m["value"]
            return lambda meta: (x := _get(meta)) is not _MISSING and x > v
        if op_ == "gte":
            v = m["value"]
            return lambda meta: (x := _get(meta)) is not _MISSING and x >= v
        if op_ == "lt":
            v = m["value"]
            return lambda meta: (x := _get(meta)) is not _MISSING and x < v
        if op_ == "lte":
            v = m["value"]
            return lambda meta: (x := _get(meta)) is not _MISSING and x <= v
        if op_ == "in":
            vals = set(m["values"])
            return lambda meta: (x := _get(meta)) in vals
        if op_ == "notin":
            vals = set(m["values"])
            return lambda meta: (x := _get(meta)) not in vals
        if op_ in {"between", "notbetween"}:
            r = m["range"]
            low, high = r.get("low"), r.get("high")
            inc_low, inc_high = r["inclusive"]["low"], r["inclusive"]["high"]

            def in_range(x):
                if x is _MISSING: return False
                if low is not None:
                    if inc_low and x < low: return False
                    if not inc_low and x <= low: return False
                if high is not None:
                    if inc_high and x > high: return False
                    if not inc_high and x >= high: return False
                return True

            return (lambda meta: in_range(_get(meta))) if op_ == "between" else (lambda meta: not in_range(_get(meta)))
    raise RuntimeError("Unreachable")
