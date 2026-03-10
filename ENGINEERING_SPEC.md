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
  - **Post-mortem exception capture** (`errsnap`)
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
    ├── errsnap/
    │   ├── __init__.py
    │   ├── _types.py
    │   ├── _capture.py
    │   ├── _writer.py
    │   ├── _reader.py
    │   └── py.typed
    └── _version.py
tests/
├── label_selector/
│   ├── test_core.py
│   └── test_label_rule.py
├── mp_logging/
│   └── test_mp_logging.py
└── errsnap/
    ├── conftest.py
    └── test_errsnap.py
docs/
├── label_selector.md
├── mp_logger.md
└── errsnap.md
```

### Core Module Responsibilities

| Module | Responsibility |
|--------|---------------|
| `label_selector.core` | Predicate compilation, rule normalization, validation |
| `label_selector.label` | Label abstraction with operator overloads |
| `label_selector.rule` | Rule composition, YAML I/O |
| `mp_logging.core` | **Process-safe logging via QueueHandler + QueueListener** |
| `mp_logging.__init__` | API surface for mp_logging |
| `errsnap._types` | `DumpMeta` frozen dataclass; JSON serialisation round-trip |
| `errsnap._writer` | Filename resolution, sequence numbering, zip archive creation |
| `errsnap._capture` | `CaptureContext` and `capture()` context manager |
| `errsnap._reader` | `DumpFile`, `load()`, `_UnpicklableState` placeholder |
| `errsnap.__init__` | Public re-exports: `capture`, `load`, `DumpFile`, `DumpMeta` |
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
| **None for errsnap** | Uses only Python stdlib |

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
| `setup_logging()` | Creates Queue + QueueListener in main process; supports global or per-package log levels |
| `configure_worker()` | Installs QueueHandler in worker processes; supports global or per-package log levels |
| `getLogger()` | Thin typed wrapper for stdlib logger |
| `LevelConfig` | Type alias for the `level` parameter of `configure_worker` |
| Convenience wrappers | `debug`, `info`, `warning`, `error`, `critical` |

### Level Configuration

Both `setup_logging` and `configure_worker` accept the same `level: LevelConfig` parameter in two forms:

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

with setup_logging(level=logging.INFO) as cfg:
    with mp.Pool(
        processes=4,
        initializer=configure_worker,
        initargs=(cfg.queue,)
    ) as pool:
        pool.map(worker_fn, items)
```

**Main — per-package levels (same config applied to both main process and workers):**
```python
level_cfg = [
    ("", logging.WARNING),      # root default
    ("disco", logging.DEBUG),   # verbose for disco
    ("urllib3", logging.ERROR), # quiet for urllib3
]

with setup_logging(level=level_cfg) as cfg:
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

## 🧱 Exception Snapshot (`errsnap`)

### Purpose

`errsnap` provides a lightweight, stdlib-only facility for capturing full post-mortem
information when an exception escapes a code block. It writes a self-contained
`.errsnap` archive containing the exception metadata, the full formatted traceback,
and a pickle of arbitrary state supplied by the caller. The dump can later be loaded
and inspected — including the live Python objects — without re-running the failing
code.

The primary use case is **debugging distributed simulation runs** where a worker
raises an exception that is difficult to reproduce interactively: the caller wraps
the critical section, passes the relevant runtime state, and gets a dump file it
can inspect offline.

### Design Principles

- Standard-library only (no runtime dependencies beyond Python ≥ 3.11)
- Single opaque state object — callers bundle multiple objects into a `dict` or
  `list` themselves; `errsnap` does not impose structure on the captured state
- Exception is **always re-raised** — `errsnap` never swallows exceptions
- Graceful pickle failure — if the state cannot be pickled, the failure is
  recorded in the metadata and the dump is still written without `state.pkl`
- Dump files are self-describing — `meta.json` is human-readable without Python

### Dump File Format

Each dump is a zip archive with a `.errsnap` extension containing three entries:

| Entry | Format | Contents |
|-------|--------|----------|
| `meta.json` | JSON | Exception type, message, source location, timestamp, pickle status |
| `traceback.txt` | Plain text | Full formatted traceback from `traceback.format_exception` |
| `state.pkl` | Pickle | `pickle.dumps(state)` — absent if pickling failed |

The zip format keeps everything in a single file with no sidecars, while
`meta.json` and `traceback.txt` remain inspectable with standard tools even when
the Python environment is unavailable.

### Filename Convention

Dump files follow the pattern:

```
<stem>_<YYYYMMDDThhmmss>_<NNN>.errsnap
```

where `<stem>` is derived from the `filename` argument (see below) and `<NNN>`
is a zero-padded three-digit sequence number that increments when earlier slots
for the same stem and timestamp are already occupied.

The `filename` argument to `capture()` is resolved as follows:

| Value passed | Behaviour |
|---|---|
| Omitted / `None` | Stem and directory derived from the caller's source file via `inspect.stack()` |
| A path ending in `.py` (e.g. `__file__`) | `.py` suffix stripped; directory of that file used |
| Any other string or `Path` | Used as the base path directly |

### Components

| Component | Description |
|----------|-------------|
| `CaptureContext` | Context manager returned by `capture()`; sets `dump_path` after handling an exception |
| `capture(state, *, filename)` | Factory function; returns a `CaptureContext` |
| `DumpMeta` | Frozen dataclass with all exception and location fields; supports `to_dict` / `from_dict` round-trip |
| `DumpFile` | Loaded dump object exposing `meta`, `traceback`, `state`, and `summary()` |
| `load(path)` | Loads a `.errsnap` file; accepts `str` or `Path` |
| `_UnpicklableState` | Internal placeholder returned by `load()` when `state.pkl` exists but cannot be unpickled in the current environment |

### Public API

```python
from tools.errsnap import capture, load

# --- Writing ---
with capture(state, filename=__file__):
    run_simulation_step()

# Passing multiple objects: wrap in a dict
with capture({"graph": graph, "params": params}, filename=__file__):
    run_simulation_step()

# filename omitted: derived from the calling module's __file__ automatically
with capture(state):
    run_simulation_step()

# Inspect where the dump landed (available after __exit__)
ctx = capture(state, filename=__file__)
with ctx:
    run_simulation_step()
# ctx.dump_path is set if an exception occurred, None otherwise

# --- Reading ---
dump = load("my_module_20250310T142301_001.errsnap")
dump.meta            # DumpMeta: exc_type, exc_message, filename, lineno, func, module, timestamp
dump.traceback       # str — full formatted traceback
dump.state           # unpickled object, or None if pickle_ok is False
print(dump.summary())  # returns a formatted multi-line string; does not print
```

### `DumpMeta` Fields

| Field | Type | Description |
|-------|------|-------------|
| `exc_type` | `str` | Fully qualified exception class, e.g. `"builtins.ValueError"` |
| `exc_message` | `str` | `str(exc)` of the raised exception |
| `filename` | `str` | Source file containing the `capture()` block |
| `lineno` | `int` | Line number of the `with capture(...)` statement |
| `func` | `str` | Enclosing function or method name |
| `module` | `str` | `__name__` of the calling scope |
| `timestamp` | `str` | UTC ISO-8601 timestamp of the dump |
| `pickle_ok` | `bool` | `True` if `state.pkl` was written successfully |
| `pickle_error` | `str \| None` | Reason string if pickling failed, else `None` |
| `errsnap_version` | `str` | Format version tag for forward compatibility |

### Error Handling

- If `pickle.dumps(state)` raises, `pickle_ok` is set to `False`, `pickle_error`
  records the exception description, and `state.pkl` is omitted from the archive.
  The dump is still written and the original exception is still re-raised.
- If `state.pkl` is present in the archive but `pickle.loads` fails at read time
  (e.g. the required class is not importable in the reading environment),
  `dump.state` is set to an `_UnpicklableState` instance carrying the raw bytes
  and a reason string rather than raising.

### MyPy

`errsnap` is fully typed and ships a `py.typed` marker (PEP 561).
Strict mypy rules apply:

```toml
[[tool.mypy.overrides]]
module = "tools.errsnap.*"
disallow_untyped_defs = true
disallow_incomplete_defs = true
no_implicit_reexport = true
```

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
- `errsnap` tests under `tests/errsnap/test_errsnap.py` — flat pytest (no test classes)

### MyPy
`mp_logging` and `errsnap` use strict rules:

```toml
[[tool.mypy.overrides]]
module = "tools.mp_logging.*"
disallow_untyped_defs = true
disallow_incomplete_defs = true
no_implicit_reexport = true

[[tool.mypy.overrides]]
module = "tools.errsnap.*"
disallow_untyped_defs = true
disallow_incomplete_defs = true
no_implicit_reexport = true
```

---

## 🚀 Release and Publishing

(unchanged — GitHub Actions with OIDC Trusted Publishing)

---

## 🔒 Security & Compliance

- Apache 2.0 License  
- No secrets  
- Code scanning compatible  
- Dependencies pinned  
- `errsnap` uses `pickle` for state serialisation; dump files should be treated
  as untrusted input and loaded only from known-safe sources.

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
- `docs/errsnap.md`  
- PyPI publishing docs  
- Python logging cookbook  

---

**Last Updated:** 2026-03-10  
**Maintainer:** Michiel Jansen