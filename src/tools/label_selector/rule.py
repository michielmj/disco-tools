"""
label_selector.rule
-------------------

Defines the `Rule` class — an immutable, composable representation of
selection logic built from `Label` expressions.

Features:
- Logical composition with operators:
    + or &  → AND
    |       → OR
    ~       → NOT
- Serialization: `to_dict()`, `to_yaml()`, `from_yaml()`
- Execution: `compile()` returns a fast predicate(meta) -> bool
- Lazy iteration: `select()` yields matching items from a collection

Typical usage:
    >>> from label_selector import Label
    >>> r1 = Label("env").eq("prod")
    >>> r2 = Label("version").gte(10)
    >>> selector = r1 + r2
    >>> pred = selector.compile()
    >>> pred({"env": "prod", "version": 12})
    True
"""
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Iterator
import yaml

from .core import Json, normalize, compile_node


@dataclass(frozen=True)
class Rule:
    spec: Json

    # AND with +
    def __add__(self, other: "Rule") -> "Rule":
        a, b = self.spec, other.spec
        if "all" in a and "all" in b:   return Rule({"all": a["all"] + b["all"]})
        if "all" in a:                  return Rule({"all": a["all"] + [b]})
        if "all" in b:                  return Rule({"all": [a] + b["all"]})
        return Rule({"all": [a, b]})

    # AND with &
    def __and__(self, other: "Rule") -> "Rule":
        return self + other

    # OR with |
    def __or__(self, other: "Rule") -> "Rule":
        a, b = self.spec, other.spec
        if "any" in a and "any" in b:   return Rule({"any": a["any"] + b["any"]})
        if "any" in a:                  return Rule({"any": a["any"] + [b]})
        if "any" in b:                  return Rule({"any": [a] + b["any"]})
        return Rule({"any": [a, b]})

    # NOT with ~
    def __invert__(self) -> "Rule":
        return Rule({"not": self.spec})

    # Serialization
    def to_dict(self) -> Json:
        return self.spec

    def to_yaml(self) -> str:
        return yaml.safe_dump(self.spec, sort_keys=False)

    @classmethod
    def from_yaml(cls, s: str) -> "Rule":
        return cls(yaml.safe_load(s))

    # Execution
    def compile(self) -> Callable[[Dict[str, Any]], bool]:
        return compile_node(normalize(self.spec))

    # Lazy selection (iterator)
    def select(self, items: Iterable[Dict[str, Any]]) -> Iterator[Dict[str, Any]]:
        pred = self.compile()
        return (m for m in items if pred(m))
