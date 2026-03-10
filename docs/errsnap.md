# 🪤 errsnap — Exception Snapshots

**`tools.errsnap`** is a lightweight, dependency‑free utility for capturing full
post-mortem information when an exception escapes a code block.

It writes a self-contained `.errsnap` archive containing the exception metadata,
the full formatted traceback, and a pickle of any runtime state you choose to
provide. The dump can be loaded and inspected later — including live Python
objects — without re-running the failing code.

`errsnap` is designed for situations that are hard to reproduce interactively:
distributed simulation workers, long-running batch jobs, or multi-process
pipelines where an unexpected failure would otherwise leave little evidence.

---

## 🚀 Key Features

- 🪤 **Full post-mortem capture** — exception metadata, traceback, and arbitrary state in one file
- 🔌 **Zero external dependencies** — pure Python standard library
- 🧪 **Typed** — strict MyPy compliance, ships `py.typed`
- 🔁 **Always re-raises** — never swallows exceptions; transparent to the caller
- 🛡️ **Graceful pickle failure** — if state cannot be pickled the dump is still written, minus the state
- 🔍 **Self-describing format** — `meta.json` and `traceback.txt` are readable without Python

---

## ⚡ Why You Need This

When a simulation worker raises an exception inside a distributed run it is often
not reproducible on demand: the inputs, random seeds, and intermediate state that
led to the failure are gone. `errsnap` gives you a snapshot of that exact moment,
stored next to your source file, ready to open in a notebook or debugger.

---

## 🔧 Quick Example

```python
import logging
from tools.errsnap import capture

logger = logging.getLogger(__name__)

def run_partition(graph, params):
    with capture({"graph": graph, "params": params}, filename=__file__, logger=logger):
        _do_heavy_work(graph, params)
```

If `_do_heavy_work` raises, a message like the following is emitted at `DEBUG` level:

```
errsnap: dump written to /cwd/run_partition_20250310T142301_001.errsnap (KeyError: 'missing_node')
```

If the state dict contained an unpicklable object, a second line follows:

```
errsnap: state could not be pickled — state.pkl omitted from /cwd/run_partition_20250310T142301_001.errsnap
```

If `_do_heavy_work` raises, a file such as
`run_partition_20250310T142301_001.errsnap` is written next to `run_partition.py`
and the exception propagates normally to the caller.

---

## 🧠 How It Works

```
 Your code                          errsnap
-----------                         ----------------------------------
with capture(state):       →        __enter__: record caller frame
    risky_code()           →        __exit__:  on exception:
                                      • format traceback
                                      • pickle state
                                      • write .errsnap zip
                                      • re-raise exception
```

The `.errsnap` file is a standard zip archive with three entries:

| Entry | Format | Contents |
|-------|--------|----------|
| `meta.json` | JSON | Exception type, message, source location, timestamp, pickle status |
| `traceback.txt` | Plain text | Full formatted traceback |
| `state.pkl` | Pickle | `pickle.dumps(state)` — absent if pickling failed |

---

## 🧰 API Reference

### `capture(state, *, filename=None)`

Returns a context manager. On exception: writes the dump, then re-raises.
On normal exit: does nothing (`ctx.dump_path` remains `None`).

| Parameter | Type | Description |
|-----------|------|-------------|
| `state` | `Any` | Object to snapshot. Use a `dict` or `list` to bundle multiple objects. |
| `filename` | `str \| Path \| None` | Base path for the dump file. See [Filename Resolution](#-filename-resolution) below. |
| `logger` | `logging.Logger \| None` | Optional logger. When provided, a `DEBUG` message is emitted after the dump is written. If pickling failed, a second `DEBUG` message is emitted. |

The returned `CaptureContext` exposes one attribute:

| Attribute | Type | Description |
|-----------|------|-------------|
| `dump_path` | `Path \| None` | Path of the written file; `None` if no exception occurred. |

---

### `load(path)`

Load a `.errsnap` file for inspection.

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | `str \| Path` | Path to the `.errsnap` file. |

Returns a `DumpFile`:

| Attribute | Type | Description |
|-----------|------|-------------|
| `path` | `Path` | Absolute path to the dump file. |
| `meta` | `DumpMeta` | Exception and location metadata (see below). |
| `traceback` | `str` | Full formatted traceback as a plain string. |
| `state` | `Any` | Unpickled state object, `None` if pickling failed at capture time, or `_UnpicklableState` if unpickling fails at load time. |

```python
dump.summary()  # returns a formatted multi-line string — ready to print or log
```

Raises `FileNotFoundError` if the file does not exist, `zipfile.BadZipFile` if
the archive is corrupt, and `KeyError` if required entries are missing.

---

### `DumpMeta`

Frozen dataclass with all metadata fields:

| Field | Type | Description |
|-------|------|-------------|
| `exc_type` | `str` | Fully qualified exception class, e.g. `"builtins.ValueError"` |
| `exc_message` | `str` | `str(exc)` of the raised exception |
| `filename` | `str` | Source file containing the `capture()` block |
| `lineno` | `int` | Line number of the `with capture(...)` statement |
| `func` | `str` | Enclosing function or method name |
| `module` | `str` | `__name__` of the calling scope |
| `timestamp` | `str` | UTC ISO-8601 timestamp |
| `pickle_ok` | `bool` | `True` if `state.pkl` was written successfully |
| `pickle_error` | `str \| None` | Failure description if pickling failed |
| `errsnap_version` | `str` | Format version tag for forward compatibility |

Convenience property:

```python
dump.meta.timestamp_dt  # → datetime.datetime (UTC-aware)
```

---

## 📁 Filename Resolution

The `filename` argument controls where the dump file is written and what stem it uses.

| Value passed | Behaviour |
|---|---|
| Omitted / `None` | Stem derived from the caller's `__file__` via `inspect.stack()`; dump written to **cwd** |
| A path ending in `.py` (e.g. `__file__`) | `.py` suffix stripped; dump written to **cwd** |
| Any other string or `Path` | Full path used as-is; directory component respected (defaults to cwd if bare name) |

All dump files follow the pattern:

```
<stem>_<YYYYMMDDThhmmss>_<NNN>.errsnap
```

`<NNN>` is a zero-padded three-digit sequence number that increments when earlier
slots for the same stem and timestamp are already occupied. This means rapid
consecutive failures never overwrite each other.

---

## 🔍 Inspecting a Dump

```python
from tools.errsnap import load

dump = load("my_worker_20250310T142301_001.errsnap")

# Human-readable overview
print(dump.summary())

# Exception details
print(dump.meta.exc_type)     # "builtins.KeyError"
print(dump.meta.exc_message)  # "'missing_node'"
print(dump.meta.timestamp)    # "2025-03-10T14:23:01.456789+00:00"

# Full traceback
print(dump.traceback)

# Live objects (if pickling succeeded)
if dump.meta.pickle_ok:
    graph = dump.state["graph"]
    params = dump.state["params"]
```

`dump.summary()` returns a formatted string like:

```
────────────────────────────────────────────────────────────────────────
  errsnap dump  my_worker_20250310T142301_001.errsnap
────────────────────────────────────────────────────────────────────────
  Timestamp  : 2025-03-10T14:23:01.456789+00:00
  Exception  : builtins.KeyError
  Message    : 'missing_node'
────────────────────────────────────────────────────────────────────────
  Captured at: /home/user/sim/my_worker.py:47
  Function   : run_partition
  Module     : my_worker
────────────────────────────────────────────────────────────────────────
  State      : pickled successfully  ✓
────────────────────────────────────────────────────────────────────────
  Traceback:

    Traceback (most recent call last):
      ...
    KeyError: 'missing_node'
────────────────────────────────────────────────────────────────────────
```

---

## 🛡️ Pickle Failure Handling

If `pickle.dumps(state)` raises (e.g. the state contains a lock, an open file
handle, or a lambda), `errsnap`:

- sets `meta.pickle_ok = False`
- records the failure reason in `meta.pickle_error`
- omits `state.pkl` from the archive
- still writes the dump and re-raises the original exception

At load time, `dump.state` is `None` when `meta.pickle_ok` is `False`.

If `state.pkl` is present in the archive but cannot be unpickled in the reading
environment (e.g. a required class is no longer importable), `dump.state` is set
to an `_UnpicklableState` placeholder instead of raising:

```python
from tools.errsnap._reader import _UnpicklableState

if isinstance(dump.state, _UnpicklableState):
    print(dump.state.reason)       # why unpickling failed
    print(len(dump.state.raw_bytes))  # raw bytes available for manual recovery
```

---

## 🧪 Testing with errsnap

In tests you can verify that a dump was written and inspect its contents:

```python
def test_worker_captures_on_failure(tmp_path):
    ctx = errsnap.capture({"x": 1}, filename=tmp_path / "test")
    with pytest.raises(ValueError):
        with ctx:
            raise ValueError("boom")

    assert ctx.dump_path is not None
    dump = errsnap.load(ctx.dump_path)
    assert dump.meta.exc_type == "builtins.ValueError"
    assert dump.state == {"x": 1}
```

---

## 🧩 Integration Patterns

**Simulation worker — capture node state on failure:**
```python
from tools.errsnap import capture

def step_node(node_runtime, simproc):
    state = {"node": node_runtime, "simproc": simproc}
    with capture(state, filename=__file__):
        simproc.try_next_epoch()
```

**Multiple objects — bundle into a dict:**
```python
with capture({"graph": graph, "experiment": exp, "epoch": epoch}):
    heavy_computation(graph, exp)
```

**Filename omitted — dump always lands in the current working directory:**
```python
# In src/disco/workers/partition_worker.py
with capture(worker_state):
    run_partition(assignment)
# Writes to cwd: ./partition_worker_20250310T142301_001.errsnap

# Passing __file__ behaves the same — only the stem is used, directory is cwd:
with capture(worker_state, filename=__file__):
    run_partition(assignment)
# Writes to cwd: ./partition_worker_20250310T142301_001.errsnap
```

**Custom output directory — pass a full path:**
```python
with capture(worker_state, filename="/var/log/disco/partition_worker"):
    run_partition(assignment)
# Writes: /var/log/disco/partition_worker_20250310T142301_001.errsnap
```

---

## 📦 Package Layout

```
tools/
└── errsnap/
    ├── __init__.py     # Public API: capture, load, DumpFile, DumpMeta
    ├── _types.py       # DumpMeta frozen dataclass
    ├── _capture.py     # CaptureContext and capture()
    ├── _writer.py      # Filename resolution, sequencing, zip creation
    ├── _reader.py      # DumpFile, load(), _UnpicklableState
    └── py.typed        # PEP 561 marker
tests/
└── errsnap/
    ├── conftest.py
    └── test_errsnap.py
```

---

## 🛠️ Best Practices

- Pass `filename=__file__` explicitly so dumps land predictably next to your source
- Bundle multiple objects into a `dict` with descriptive keys — it makes offline inspection much easier
- Check `meta.pickle_ok` before accessing `dump.state`
- Treat `.errsnap` files as untrusted input — `pickle.loads` executes arbitrary code; only load dumps from known-safe sources
- Add `*.errsnap` to `.gitignore` to avoid accidentally committing large dump files

---

## 📚 Reference

`tools.errsnap` documentation lives alongside:

- [`tools.label_selector`](label_selector.md)
- [`tools.mp_logging`](mp_logging.md)

errsnap is part of the **disco-tools** suite of reusable components.
