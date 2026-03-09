# ENGINEERING_SPEC.md

## 📘 Project Overview

**Project Name:** `disco-tools`  
**Description:**  
Reusable Python utilities for the *disco simulation engine* and related data pipelines.  
Provides composable, high-performance building blocks for label selection, scheduling, data transformation, simulation orchestration, and safe multi-process infrastructure.

**Owner:** Michiel Jansen  
**Repository:** https://github.com/michielmj/disco-tools  
**License:** MIT  
**Programming Language:** Python ≥ 3.11  
**Core Dependency Stack:** `numpy`, `pyyaml`

---

## 🧭 Goals and Scope

### Primary Objectives
- Deliver a **lightweight**, **dependency-minimal**, and **well-typed** toolkit.
- Provide common modules for:
  - Metadata qualification (`label_selector`)
  - Serialization (coming)
  - Generic utilities (coming)
  - **Multi-process–safe infrastructure** (e.g., mp-logging)
- Ensure compatibility with PyPI publishing workflows and CI automation.

### Non-Goals
- Heavy C++ or compiled extensions  
- Web UI or visualization components  
- Framework-specific integrations  

---

## ⚙️ Architecture Overview

### Package Layout

```
src/
└── tools/
    ├── __init__.py
    ├── label_selector/
    │   ├── __init__.py
    │   ├── core.py
    │   ├── label.py
    │   └── rule.py
    ├── mp_logging/
    │   ├── __init__.py
    │   └── core.py
    └── _version.py
tests/
├── label_selector/
│   ├── test_core.py
│   └── test_label_rule.py
└── mp_logging/
    └── test_mp_logging.py
docs/
├── label_selector.md
└── mp_logger.md
```

### Core Module Responsibilities

| Module | Responsibility |
|--------|---------------|
| `label_selector.core` | Predicate compilation, rule normalization, validation |
| `label_selector.label` | Label abstraction with operator overloads |
| `label_selector.rule` | Rule composition, YAML I/O |
| `mp_logging.core` | **Process-safe logging via QueueHandler + QueueListener** |
| `mp_logging.__init__` | API surface for mp_logging |
| `tests/` | Unit + integration tests |
| `docs/` | User + developer documentation |

---

## 🧩 Key Dependencies

| Dependency | Purpose |
|------------|---------|
| `numpy` | Numerical foundation |
| `pyyaml` | YAML I/O for rules |
| `pytest`, `pytest-cov` | Testing |
| `mypy` | Static typing |
| `twine`, `build` | Packaging |
| `types-pyyaml` | Type hints for YAML |
| **None for mp_logging** | Uses only Python stdlib |

---

## 🧱 Multi-Process Logging (`mp_logging`)

### Purpose
`mp_logging` provides a multiprocessing-safe logging facility that prevents corrupted or interleaved log output when running simulations or parallel pipelines.

### Design Principles
- Standard-library only  
- Queue-based architecture  
- Never configures global logging inside libraries  
- API compatibility with `logging`  

### Components

| Component | Description |
|----------|-------------|
| `setup_logging()` | Creates Queue + QueueListener in main process |
| `configure_worker()` | Installs QueueHandler in worker processes; supports global or per-package log levels |
| `getLogger()` | Thin typed wrapper for stdlib logger |
| `LevelConfig` | Type alias for the `level` parameter of `configure_worker` |
| Convenience wrappers | `debug`, `info`, `warning`, `error`, `critical` |

### `configure_worker` Level Configuration

The `level` parameter of `configure_worker` accepts two forms:

- **`int`** — sets the root logger globally (e.g. `logging.DEBUG`).
- **`list[tuple[str, int]]`** — per-package configuration.  Each tuple is
  `(package_name, level)`.  An empty string `""` targets the root logger.
  If no root entry is provided, the root is set to `NOTSET` so per-package
  fine-grained levels are not silently filtered before reaching the
  QueueHandler.

### Usage Pattern

**Main — global level:**
```python
from tools.mp_logging import setup_logging, configure_worker
import multiprocessing as mp

with setup_logging() as cfg:
    with mp.Pool(
        processes=4,
        initializer=configure_worker,
        initargs=(cfg.queue,)
    ) as pool:
        pool.map(worker_fn, items)
```

**Main — per-package levels:**
```python
level_cfg = [
    ("", logging.WARNING),      # root default
    ("disco", logging.DEBUG),   # verbose for disco
    ("urllib3", logging.ERROR), # quiet for urllib3
]

with setup_logging() as cfg:
    with mp.Pool(
        processes=4,
        initializer=configure_worker,
        initargs=(cfg.queue, level_cfg)
    ) as pool:
        pool.map(worker_fn, items)
```

**Worker:**
```python
logger = getLogger(__name__)
logger.info("worker started")
```

### Guarantees
- Safe concurrent writes
- Deterministic ordering via QueueListener
- Works for ETL, simulation, pipelines
- Per-package log verbosity configurable without coupling workers to handler setup

---

## 🧱 Build System

Backend: `setuptools.build_meta`  
Versioning: `setuptools-scm`  
Wheel: pure Python (`py3-none-any`)

Build:
```bash
rm -rf dist build *.egg-info
python -m pip install -U pip setuptools wheel build setuptools-scm
python -m build
python -m twine check dist/*
```

---

## 🧪 Testing and Type Checking

### Tests
- `pytest`  
- Multi-process tests under `tests/mp_logging/test_mp_logging.py`

### MyPy
`mp_logging` uses strict rules:

```
[[tool.mypy.overrides]]
module = "disco_tools.mp_logging.*"
disallow_untyped_defs = true
disallow_incomplete_defs = true
no_implicit_reexport = true
```

---

## 🚀 Release and Publishing

(unchanged — GitHub Actions with OIDC Trusted Publishing)

---

## 🔒 Security & Compliance

- MIT License  
- No secrets  
- Code scanning compatible  
- Dependencies pinned  

---

## 🧠 Development Guidelines

- PEP 8 + black  
- Explicit typing  
- High coverage  
- Conventional commits  

---

## 📚 References

- `docs/mp_logger.md`  
- `docs/label_selector.md`  
- PyPI publishing docs  
- Python logging cookbook  

---

**Last Updated:** 2026-03-09
**Maintainer:** Michiel Jansen  
