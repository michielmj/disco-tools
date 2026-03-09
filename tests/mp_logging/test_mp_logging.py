from __future__ import annotations

import logging
import multiprocessing as mp
import time
from typing import List

from tools.mp_logging import (
    LevelConfig,
    MPLoggingConfig,
    configure_worker,
    getLogger,
    setup_logging,
)
from tools.mp_logging.core import LogQueue


class ListHandler(logging.Handler):
    """Simple handler that collects log records in a list."""

    def __init__(self, storage: List[logging.LogRecord]) -> None:
        super().__init__()
        self._storage = storage

    def emit(self, record: logging.LogRecord) -> None:
        self._storage.append(record)


def _worker(queue: LogQueue, message: str) -> None:
    """Worker function for multiprocessing tests."""
    configure_worker(queue)
    logger = getLogger(__name__)
    logger.info("worker: %s", message)


def test_setup_logging_int_level() -> None:
    """setup_logging with an int level sets the root logger globally."""
    null = logging.NullHandler()
    with setup_logging(level=logging.DEBUG, handlers=[null]):
        assert logging.getLogger().level == logging.DEBUG


def test_setup_logging_per_package_levels() -> None:
    """setup_logging with a list sets per-package levels in the main process."""
    null = logging.NullHandler()
    level_config = [
        ("", logging.WARNING),
        ("disco", logging.DEBUG),
    ]
    with setup_logging(level=level_config, handlers=[null]):
        assert logging.getLogger().level == logging.WARNING
        assert logging.getLogger("disco").level == logging.DEBUG


def test_setup_logging_per_package_no_root_entry() -> None:
    """Without a root entry, root defaults to NOTSET (pass-through)."""
    null = logging.NullHandler()
    with setup_logging(level=[("disco", logging.DEBUG)], handlers=[null]):
        assert logging.getLogger().level == logging.NOTSET
        assert logging.getLogger("disco").level == logging.DEBUG


def test_single_process_logging_compatibility() -> None:
    """getLogger should behave like logging.getLogger in single-process mode."""
    logger = getLogger(__name__)
    assert isinstance(logger, logging.Logger)

    # Smoke test: just ensure this doesn't raise.
    logger.debug("single-process debug message")
    logger.info("single-process info message")


def test_multiprocess_logging_collects_records() -> None:
    """Logs from multiple processes should be collected via the queue listener."""
    records: List[logging.LogRecord] = []
    handler = ListHandler(records)

    messages = ["alpha", "beta", "gamma"]

    with setup_logging(level=logging.INFO, handlers=[handler]) as cfg:
        _run_workers(cfg, messages)

        # Give the QueueListener a brief moment to drain the queue.
        time.sleep(0.2)

    # We expect at least one record per message.
    # (Some environments may add extra records, so we don't check equality.)
    assert len(records) >= len(messages)

    # Extract rendered messages for easier assertion.
    rendered = [handler.format(r) for r in records]

    for m in messages:
        # Each worker logs "worker: <message>"
        assert any(m in line for line in rendered), f"Missing log for {m!r}"


def _worker_with_level(
    queue: LogQueue, message: str, level: LevelConfig
) -> None:
    """Worker that uses a custom level config."""
    configure_worker(queue, level=level)
    logging.getLogger("disco").debug("disco-debug: %s", message)
    logging.getLogger("disco").info("disco-info: %s", message)
    logging.getLogger("other").debug("other-debug: %s", message)
    logging.getLogger("other").info("other-info: %s", message)


def test_configure_worker_int_level() -> None:
    """An int level sets the root logger globally."""
    records: List[logging.LogRecord] = []
    handler = ListHandler(records)

    with setup_logging(level=logging.DEBUG, handlers=[handler]) as cfg:
        p = mp.Process(
            target=_worker_with_level,
            args=(cfg.queue, "msg", logging.DEBUG),
        )
        p.start()
        p.join(timeout=5.0)
        assert not p.is_alive()
        time.sleep(0.2)

    names = {r.name for r in records}
    # Both loggers should have emitted records at DEBUG level.
    assert "disco" in names
    assert "other" in names
    msgs = [handler.format(r) for r in records]
    assert any("disco-debug" in m for m in msgs)
    assert any("other-debug" in m for m in msgs)


def test_configure_worker_per_package_levels() -> None:
    """A list of (package, level) tuples sets levels per package."""
    records: List[logging.LogRecord] = []
    handler = ListHandler(records)

    level_config = [
        ("", logging.WARNING),   # root: only WARNING and above
        ("disco", logging.DEBUG),  # disco: DEBUG and above
    ]

    with setup_logging(level=logging.DEBUG, handlers=[handler]) as cfg:
        p = mp.Process(
            target=_worker_with_level,
            args=(cfg.queue, "msg", level_config),
        )
        p.start()
        p.join(timeout=5.0)
        assert not p.is_alive()
        time.sleep(0.2)

    msgs = [handler.format(r) for r in records]
    # disco should emit DEBUG messages.
    assert any("disco-debug" in m for m in msgs), "Expected disco DEBUG record"
    assert any("disco-info" in m for m in msgs), "Expected disco INFO record"
    # other logger is filtered by root WARNING level — no debug or info.
    assert not any("other-debug" in m for m in msgs), "Unexpected other DEBUG record"
    assert not any("other-info" in m for m in msgs), "Unexpected other INFO record"


def test_configure_worker_per_package_no_root_entry() -> None:
    """Without a root entry, the root level defaults to NOTSET (pass-through)."""
    records: List[logging.LogRecord] = []
    handler = ListHandler(records)

    # Only set disco to DEBUG; no root entry.
    level_config = [("disco", logging.DEBUG)]

    with setup_logging(level=logging.DEBUG, handlers=[handler]) as cfg:
        p = mp.Process(
            target=_worker_with_level,
            args=(cfg.queue, "msg", level_config),
        )
        p.start()
        p.join(timeout=5.0)
        assert not p.is_alive()
        time.sleep(0.2)

    msgs = [handler.format(r) for r in records]
    # disco DEBUG records must be present.
    assert any("disco-debug" in m for m in msgs), "Expected disco DEBUG record"
    # other logger is not explicitly restricted, so INFO passes through.
    assert any("other-info" in m for m in msgs), "Expected other INFO record"


def _run_workers(cfg: MPLoggingConfig, messages: list[str]) -> None:
    """Helper to start and join worker processes."""
    processes: list[mp.Process] = []

    for msg in messages:
        p = mp.Process(target=_worker, args=(cfg.queue, msg))
        p.start()
        processes.append(p)

    for p in processes:
        p.join(timeout=5.0)
        assert not p.is_alive(), "Worker process did not terminate in time"
