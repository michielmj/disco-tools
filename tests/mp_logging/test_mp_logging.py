from __future__ import annotations

import logging
import multiprocessing as mp
import time
from typing import List

from tools.mp_logging import (
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
