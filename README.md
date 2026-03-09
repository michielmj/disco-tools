# 🧾 disco-tools

**Common tools for disco simulation engine.**  

[![PyPI](https://img.shields.io/pypi/v/disco-tools.svg)](https://pypi.org/project/disco-tools/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Build](https://github.com/michielmj/disco-tools/actions/workflows/build.yml/badge.svg)](https://github.com/michielmj/disco-tools/actions)
[![Tests](https://github.com/michielmj/disco-tools/actions/workflows/test.yml/badge.svg)](https://github.com/michielmj/disco-tools/actions)

---

## 🧭 Overview

`disco-tools` is a collection of reusable Python utilities supporting simulation, analytics, and data-driven decision systems.  
It provides modular building blocks for working with metadata, scheduling, simulation orchestration, and system integration.

Each tool is designed to be:
- **Lightweight** — minimal dependencies
- **Composable** — works as a standalone library or inside larger systems
- **Fast** — optimized for high-throughput, data-heavy environments

Documentation for individual modules is available in the [`docs/`](docs) folder.

---

## ✨ Features

- ⚙️ **Label Selector** — Fast rule engine for qualifying and filtering metadata.  
  → [Read documentation ›](docs/label_selector.md)

- ⚙️ **Multi-Process Logging** — Safe, queue-based logging across worker processes using Python’s 
- `QueueHandler` + `QueueListener`.  
  → [Read documentation ›](docs/mp_logging.md)

---

## 🚀 Installation

```bash
pip install disco-tools
```

---

## 🧰 Development Setup

Clone and install in editable mode:

```bash
git clone https://github.com/michielmj/disco-tools.git
cd disco-tools
pip install -e .[dev]
```

Run all tests:

```bash
pytest -q
```

---

## 📚 Documentation

- [Label Selector](docs/label_selector.md) — fast, composable rule engine for key–value metadata  
- Additional module docs will be added under the [`docs/`](docs) directory as the toolkit evolves.

---

## 🧪 Example Usage

```python
from disco_tools.label_selector import Label, qualifies

rule = (Label("env") == "prod") + Label("version").gte(10)
meta = {"env": "prod", "version": 12}

if qualifies(meta, rule):
    print("Match!")
```

---

## 🧾 License

MIT License © 2025 — part of the **disco-tools** project.
