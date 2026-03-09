# 🧱 Multi-Process Logging

**`tools.mp_logging`** provides a lightweight, dependency‑free, **process‑safe logging system** built on top of Python’s standard `logging` library.

It ensures that logs produced from multiple worker processes (e.g., using `multiprocessing.Pool`) remain **ordered, uncorrupted, and easy to configure**, using a central QueueListener and worker-side QueueHandlers.

This module is ideal for simulation engines, ETL pipelines, schedulers, and high‑throughput analytics where multiple processes must emit logs safely.

---

## 🚀 Key Features

- 🧵 **Process‑safe logging** using a central QueueListener  
- 🔌 **Zero external dependencies** — pure Python standard library  
- 🧱 **API‑compatible** with standard `logging.getLogger()`  
- 🧪 **Typed** — strict MyPy compliance  
- 🧲 **Centralized handler setup** — workers never touch log files directly  
- 📦 **Drop‑in utility** for multiprocessing‑based systems  

---

## ⚡ Why You Need This

The standard Python logging module is **thread‑safe** but **not process‑safe**.  
When multiple worker processes write to the same file handler:

- Lines get **interleaved**
- Outputs become **corrupted**
- Race conditions appear under high load

`tools.mp_logging` solves this by sending logs through a multiprocessing queue to a single, centralized listener in the master process.

---

## 🔧 Quick Example

```python
import multiprocessing as mp
from tools.mp_logging import setup_logging, configure_worker, getLogger

def worker(i: int) -> None:
    logger = getLogger(__name__)
    logger.info(f"Working on item {i}")

if __name__ == "__main__":
    with setup_logging() as cfg:
        with mp.Pool(
            processes=4,
            initializer=configure_worker,
            initargs=(cfg.queue,)
        ) as pool:
            pool.map(worker, range(10))
```

---

## 🧠 How It Works

Internally, the module uses this architecture:

```
 Workers                           Main Process
----------                         ------------------------------
QueueHandler -> mp.Queue -> QueueListener -> Stream/File Handlers
```

### **In workers**
- A `QueueHandler` forwards `LogRecord` objects to the shared queue.
- Workers do *not* configure any handlers.

### **In the main process**
- A `QueueListener` receives all log records.
- Your desired handlers (console, file, rotating file, etc.) are attached only here.
- Logs are written in deterministic order.

---

## 🧰 Functional API

### `setup_logging(level=logging.INFO, handlers=None, queue=None)`
Initialize the logging system in the **main process**.

- Creates a `multiprocessing.Queue[LogRecord]`
- Starts a QueueListener that forwards logs to handlers
- Returns a `MPLoggingConfig` object with:
  - `queue`
  - `listener`

### `configure_worker(queue, level=logging.INFO, keep_existing_handlers=False)`
Prepare a worker process for safe logging.

- Installs a `QueueHandler`
- Removes other handlers unless explicitly kept

The `level` parameter accepts two forms:

| Form | Type | Effect |
|------|------|--------|
| Global level | `int` | Sets the root logger to that level (e.g. `logging.DEBUG`) |
| Per-package list | `list[tuple[str, int]]` | Sets each `(package, level)` pair individually |

An empty string `""` in a per-package list targets the root logger.  If no
root entry is provided the root is set to `NOTSET` so per-package `DEBUG`
settings are not silently filtered.

```python
# Global level — existing behaviour
configure_worker(queue, level=logging.DEBUG)

# Per-package levels
configure_worker(queue, level=[
    ("", logging.WARNING),      # root default: WARNING and above
    ("disco", logging.DEBUG),   # verbose for disco package
    ("urllib3", logging.ERROR), # quiet for urllib3
])
```

### `getLogger(name=None)`
Thin wrapper around `logging.getLogger`.  
Use exactly like the standard logging API.

### Root-level convenience functions
These mirror Python logging:

- `debug()`
- `info()`
- `warning()`
- `error()`
- `exception()`
- `critical()`

---

## 🧪 Testing Example

A minimal multi-process test:

```python
from tools.mp_logging import setup_logging, configure_worker, getLogger
import multiprocessing as mp

def worker(q):
    configure_worker(q)
    getLogger(__name__).info("hello from worker")

def test():
    with setup_logging() as cfg:
        p = mp.Process(target=worker, args=(cfg.queue,))
        p.start()
        p.join()
```

---

## 📦 Package Layout

```
tools/
└── mp_logging/
    ├── __init__.py         # Public API (getLogger, setup_logging, ...)
    └── core.py             # Typed queue-based logging implementation
tests/
└── mp_logging/
    └── test_mp_logging.py
```

---

## 🧩 Integration Ideas

Use mp_logging whenever you have:

- A simulation engine with parallel workers  
- Worker‑based ETL or computation pipelines  
- A data logger that must aggregate events from several processes  
- Multiprocessing schedulers or batch workers  
- Any workload that writes logs from multiple processes  

---

## 🛠️ Best Practices

- Configure logging **once** in the main process
- Workers should always call `configure_worker(queue)`
- Avoid heavy formatting in workers — let the listener handle it
- Use JSON or structured logging handlers on the main process for analytics pipelines
- When using per-package levels, include a `("", level)` root entry to set an explicit default; omitting it leaves the root at `NOTSET` which passes everything through to the QueueHandler

---

## 📚 Reference

`tools.mp_logging` documentation lives alongside:

- [`tools.label_selector`](label_selector.md)
- Shared simulation utilities (coming soon)

mp_logging is part of the **disco-tools** suite of reusable components.

