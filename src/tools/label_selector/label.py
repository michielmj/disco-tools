"""
label_selector.label
--------------------

Defines the `Label` class — a lightweight factory for creating atomic rules
against key–value metadata.

`Label` objects support both operator overloads and explicit function calls:
    - Operators:  ==, !=, >, >=, <, <=
    - Methods:    .eq(), .ne(), .gt(), .gte(), .lt(), .lte(),
                  .isin(), .notin(), .exists(), .between()

All generated rules only accept JSON/YAML primitive values (None, bool, int, float, str).

Usage example:
    >>> from label_selector import Label
    >>> rule = Label("env") == "prod"
    >>> print(rule.to_dict())
    {'match': {'key': 'env', 'op': 'eq', 'value': 'prod'}}
"""
from dataclasses import dataclass
from typing import Any, Iterable

from .core import Json, validate_primitive, validate_primitive_list
from .rule import Rule


@dataclass(frozen=True)
class Label:
    key: str

    # Operator forms (delegate to explicit methods to share validation)
    def __eq__(self, v: Any) -> Rule:  # type: ignore[override]
        return self.eq(v)

    def __ne__(self, v: Any) -> Rule:  # type: ignore[override]
        return self.ne(v)

    def __gt__(self, v: Any) -> Rule:
        return self.gt(v)

    def __ge__(self, v: Any) -> Rule:
        return self.gte(v)

    def __lt__(self, v: Any) -> Rule:
        return self.lt(v)

    def __le__(self, v: Any) -> Rule:
        return self.lte(v)

    # Function forms (validated JSON primitives only)
    def eq(self, v: Any) -> Rule:
        v = validate_primitive(v)
        return Rule({"match": {"key": self.key, "op": "eq", "value": v}})

    def ne(self, v: Any) -> Rule:
        v = validate_primitive(v)
        return Rule({"match": {"key": self.key, "op": "ne", "value": v}})

    def gt(self, v: Any) -> Rule:
        v = validate_primitive(v)
        return Rule({"match": {"key": self.key, "op": "gt", "value": v}})

    def gte(self, v: Any) -> Rule:
        v = validate_primitive(v)
        return Rule({"match": {"key": self.key, "op": "gte", "value": v}})

    def lt(self, v: Any) -> Rule:
        v = validate_primitive(v)
        return Rule({"match": {"key": self.key, "op": "lt", "value": v}})

    def lte(self, v: Any) -> Rule:
        v = validate_primitive(v)
        return Rule({"match": {"key": self.key, "op": "lte", "value": v}})

    def isin(self, values: Iterable[Any]) -> Rule:
        vals = validate_primitive_list(values)
        return Rule({"match": {"key": self.key, "op": "in", "values": vals}})

    def notin(self, values: Iterable[Any]) -> Rule:
        vals = validate_primitive_list(values)
        return Rule({"match": {"key": self.key, "op": "notin", "values": vals}})

    def exists(self) -> Rule:
        return Rule({"match": {"key": self.key, "op": "exists"}})

    def between(self, low=None, high=None, inc_low=True, inc_high=True) -> Rule:
        if low is None and high is None:
            raise ValueError("between(): low or high must be provided")
        if low is not None:
            low = validate_primitive(low, "range.low")
        if high is not None:
            high = validate_primitive(high, "range.high")
        return Rule({
            "match": {
                "key": self.key,
                "op": "between",
                "range": {
                    "low": low,
                    "high": high,
                    "inclusive": {"low": inc_low, "high": inc_high},
                },
            }
        })
