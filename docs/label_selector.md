# 🏷️ Label Selector

**`tools.label_selector`** is a lightweight, dependency-free rule engine for evaluating and filtering
metadata dictionaries using Kubernetes-style label semantics.

It provides a fast, composable way to define and combine logical rules for
key–value pairs — useful for selecting, routing, or grouping data anywhere
you have labeled entities.

---

## 🚀 Key Features

- ⚡ **Fast**: compiled to short-circuiting Python callables (millions of evaluations/sec)
- 🧱 **Composable logic**:
  - `+` or `&` → **AND**
  - `|` → **OR**
  - `~` → **NOT**
- 💬 **Two syntaxes**:
  - Operator form: `Label("a") > 5`
  - Functional form: `Label("a").gt(5)`
- 🧩 **YAML/JSON serializable** — easy to persist and reload rules
- 💤 **Lazy filtering**: `select()` yields an iterator
- 🔒 **Strict type validation**: values must be JSON/YAML primitives  
  (`str`, `int`, `float`, `bool`, or `None`)

---

## 🔧 Quick Example

```python
from tools.label_selector import Label, qualifies, select

# Define atomic rules
rule1 = Label("env").eq("prod")
rule2 = Label("version") >= 10

# Combine with logical operators
selector = rule1 + rule2   # AND
alt_selector = rule1 | rule2  # OR

# Qualify a single metadata object
meta = {"env": "prod", "version": 12}
print(qualifies(meta, selector))  # True

# Lazy filtering across a collection
items = [
    {"id": 1, "env": "prod", "version": 9},
    {"id": 2, "env": "staging", "version": 11},
    {"id": 3, "env": "prod", "version": 12},
]

for obj in select(items, selector):
    print(obj["id"])  # -> 3
```

---

## 🧠 Functional Composition Helpers

Instead of chaining operators, you can build rules dynamically:

```python
from tools.label_selector import all_, any_, not_, Label

rule = all_(
    Label("env").isin(["prod", "staging"]),
    any_(
        Label("version").gte(10),
        Label("tag").eq("blue")
    ),
    not_(Label("region").isin(["cn-north-1"]))
)
```

Equivalent YAML structure:

```yaml
all:
  - match: { key: env, op: in, values: [prod, staging] }
  - any:
      - match: { key: version, op: gte, value: 10 }
      - match: { key: tag, op: eq, value: blue }
  - not:
      match: { key: region, op: in, values: [cn-north-1] }
```

---

## 📄 YAML / JSON Integration

Rules can be serialized and re-loaded for configuration-driven selection:

```python
from tools.label_selector import Label, Rule

rule = Label("priority").between(5, 10)
yaml_str = rule.to_yaml()
print(yaml_str)

same_rule = Rule.from_yaml(yaml_str)
assert rule.to_dict() == same_rule.to_dict()
```

---

## ⚙️ API Overview

| Object | Description |
|---------|--------------|
| **`Label(key)`** | Create an atomic rule builder for a given key. |
| **Operators** | `==`, `!=`, `>`, `>=`, `<`, `<=` |
| **Methods** | `.eq()`, `.ne()`, `.gt()`, `.gte()`, `.lt()`, `.lte()`, `.isin()`, `.notin()`, `.exists()`, `.between()` |
| **`Rule`** | Composable logical object (supports `+`, `|`, `~`) with `.compile()`, `.select()`, `.to_yaml()`, `.from_yaml()`. |
| **`compile(rule)`** | Return a fast predicate: `meta -> bool`. |
| **`qualifies(meta, rule)`** | Check if a single metadata object matches a rule. |
| **`select(items, rule)`** | Lazily yield matching items from an iterable. |
| **`all_(*rules)`**, **`any_(*rules)`**, **`not_(rule)`** | Functional equivalents of `+`, `|`, `~`. |

---

## 🧩 Integration Ideas

The label selector can be used anywhere metadata-based filtering is needed:

- Selecting entities in simulations or digital twins  
- Filtering datasets, job definitions, or events by tags  
- Implementing feature toggles, routing rules, or matching logic in services  
- Replacing ad-hoc filtering logic in configuration-driven systems

---

## 🧰 Package Layout

```
tools/
└── label_selector/
    ├── __init__.py          # Public API (Label, Rule, helpers)
    ├── core.py              # Internal compiler, normalization, and validation
    ├── label.py             # Label class and atomic rule creation
    ├── rule.py              # Rule class, logic composition, YAML I/O
tests/
└── label_selector/
    ├── test_core.py
    └── test_label_rule.py
```
