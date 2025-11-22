"""
label_selector
--------------

Public API for the Label Selector rule engine.

Exposes:
    - `Label` and `Rule` classes
    - Functional helpers: `compile()`, `qualifies()`, `select()`
    - Logical combinators: `all_()`, `any_()`, `not_()`

The label selector is a generic, dependency-free, high-performance tool for
evaluating or filtering metadata dictionaries based on composable rules.

Typical usage:
    >>> from tools.label_selector import Label, select
    >>> rule = (Label("env") == "prod") + Label("version").gte(10)
    >>> items = [{"env": "prod", "version": 9}, {"env": "prod", "version": 12}]
    >>> for obj in select(items, rule):
    ...     print(obj)
    {'env': 'prod', 'version': 12}
"""

from typing import Any, Callable, Dict, Iterable, Iterator, Sequence, Union

from .label import Label
from .rule import Rule
from .core import Json, Primitive, normalize as _normalize, compile_node as _compile_node

__all__ = [
    "Label",
    "Rule",
    "Primitive",
    "Json",
    "compile",
    "qualifies",
    "select",
    "all_",
    "any_",
    "not_",
    "__version__",
]

__version__ = "0.1.0"

_RuleLike = Union[Rule, Dict[str, Any]]


def _to_rule(rule: _RuleLike) -> Rule:
    return rule if isinstance(rule, Rule) else Rule(rule)


def compile(rule: _RuleLike) -> Callable[[Dict[str, Any]], bool]:
    """
    Compile a Rule or raw spec dict into a fast predicate(meta)->bool.
    Note: For hot paths, compile once and reuse the returned callable.
    """
    r = _to_rule(rule)
    return _compile_node(_normalize(r.to_dict()))


def qualifies(meta: Dict[str, Any], rule: _RuleLike) -> bool:
    """Return True if `meta` satisfies `rule`, else False."""
    return compile(rule)(meta)


def select(items: Iterable[Dict[str, Any]], rule: _RuleLike) -> Iterator[Dict[str, Any]]:
    """
    Lazily yield items from `items` that satisfy `rule`.
    Equivalent to `r.select(items)` but accepts a raw dict too.
    """
    pred = compile(rule)
    return (m for m in items if pred(m))


def all_(*rules: _RuleLike) -> Rule:
    """
    Functional AND: all_(r1, r2, ...) -> Rule with {"all":[...]}.
    Flattens nested ANDs when inputs are Rules already composed with AND.
    """
    specs = []
    for rl in rules:
        r = _to_rule(rl)
        d = r.to_dict()
        if "all" in d:
            specs.extend(d["all"])
        else:
            specs.append(d)
    return Rule({"all": specs}) if specs else Rule({"all": []})


def any_(*rules: _RuleLike) -> Rule:
    """
    Functional OR: any_(r1, r2, ...) -> Rule with {"any":[...]}.
    Flattens nested ORs when inputs are Rules already composed with OR.
    """
    specs = []
    for rl in rules:
        r = _to_rule(rl)
        d = r.to_dict()
        if "any" in d:
            specs.extend(d["any"])
        else:
            specs.append(d)
    return Rule({"any": specs}) if specs else Rule({"any": []})


def not_(rule: _RuleLike) -> Rule:
    """Functional NOT: not_(r) -> ~r."""
    return ~_to_rule(rule)
