from __future__ import annotations

"""
Generic multi-process logging helpers.

Usage (main process):

    import multiprocessing as mp
    from disco_tools.mp_logging import setup_logging, configure_worker, getLogger

    def _worker_init(queue: LogQueue) -> None:
        configure_worker(queue)

    def worker_task(i: int) -> None:
        logger = getLogger(__name__)
        logger.info("Processing item %s", i)

    if __name__ == "__main__":
        with setup_logging(level=logging.INFO) as cfg:
            logger = getLogger(__name__)
            logger.info("Starting pool")

            with mp.Pool(
                processes=4,
                initializer=_worker_init,
                initargs=(cfg.queue,),
            ) as pool:
                pool.map(worker_task, range(10))

This module only depends on the standard library.
"""

import contextlib
import logging
import logging.handlers
import multiprocessing as mp
from dataclasses import dataclass
from multiprocessing.queues import Queue as MPQueue
from typing import Any, Iterable, Iterator, Optional, TypeAlias, Union


# NOTE: multiprocessing.Queue is not generic in typeshed (Py ≤ 3.12),
# so we alias the concrete Queue type instead of using Queue[LogRecord].
LogQueue: TypeAlias = MPQueue
LevelConfig: TypeAlias = Union[int, list[tuple[str, int]]]


def _apply_level_config(level: LevelConfig) -> None:
    """Apply a LevelConfig to the current process's loggers.

    - ``int``: sets the root logger level globally.
    - ``list[tuple[str, int]]``: sets per-package levels.  An empty string
      ``""`` targets the root logger.  If no root entry is provided the root
      is set to ``NOTSET`` so per-package DEBUG settings are not filtered out
      at the root before reaching any handlers.
    """
    if isinstance(level, int):
        logging.getLogger().setLevel(level)
    else:
        root_level_set = False
        for package, pkg_level in level:
            if package == "":
                logging.getLogger().setLevel(pkg_level)
                root_level_set = True
            else:
                logging.getLogger(package).setLevel(pkg_level)
        if not root_level_set:
            logging.getLogger().setLevel(logging.NOTSET)


@dataclass
class MPLoggingConfig:
    """
    Holds the objects created by setup_logging.

    Attributes
    ----------
    queue:
        The multiprocessing.Queue used to dispatch LogRecord objects
        from worker processes to the listener.
    listener:
        The QueueListener instance. Normally you don't need to touch this
        directly; just rely on the context manager.
    """
    queue: LogQueue
    listener: logging.handlers.QueueListener


@contextlib.contextmanager
def setup_logging(
    level: LevelConfig = logging.INFO,
    handlers: Optional[Iterable[logging.Handler]] = None,
    queue: Optional[LogQueue] = None,
) -> Iterator[MPLoggingConfig]:
    """
    Configure logging for the main process using a QueueListener.

    - Creates a multiprocessing.Queue (or uses the one you pass in).
    - Attaches a QueueListener that forwards records to the given handlers.
    - Returns an MPLoggingConfig with (queue, listener).
    - On exit, stops the listener cleanly.

    This is meant to be called once, in the main process.

    Parameters
    ----------
    level:
        Logging level configuration.  Two forms are accepted:

        - ``int``: sets the root logger level globally, e.g. ``logging.INFO``.
        - ``list[tuple[str, int]]``: per-package configuration.  Each tuple is
          ``(package_name, level)``.  An empty string ``""`` targets the root
          logger.  If no root entry is provided, the root is set to ``NOTSET``
          so that per-package fine-grained levels are not filtered out.

    handlers:
        Handlers attached to the QueueListener in the main process.  Defaults
        to a single StreamHandler with a standard formatter.
    queue:
        Supply an existing multiprocessing.Queue to reuse it.  A new queue is
        created when this is ``None`` (the default).
    """
    if queue is None:
        log_queue: LogQueue = mp.Queue()
    else:
        log_queue = queue

    if handlers is None:
        default_handler = logging.StreamHandler()
        default_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] "
                "[%(processName)s] [%(threadName)s] "
                "%(name)s: %(message)s"
            )
        )
        resolved_handlers: Iterable[logging.Handler] = (default_handler,)
    else:
        resolved_handlers = handlers

    _apply_level_config(level)

    listener = logging.handlers.QueueListener(
        log_queue, *resolved_handlers, respect_handler_level=True
    )
    listener.start()

    cfg = MPLoggingConfig(queue=log_queue, listener=listener)

    try:
        yield cfg
    finally:
        listener.stop()


def configure_worker(
    queue: LogQueue,
    level: LevelConfig = logging.INFO,
    keep_existing_handlers: bool = False,
) -> None:
    """
    Configure logging in a worker process to send all records to the queue.

    Typically used as multiprocessing initializer:

        def _worker_init(queue: LogQueue) -> None:
            configure_worker(queue)

    Parameters
    ----------
    queue:
        The multiprocessing.Queue created in setup_logging.
    level:
        Logging level configuration. Two forms are accepted:

        - ``int``: sets the root logger level globally, e.g. ``logging.DEBUG``.
        - ``list[tuple[str, int]]``: a list of ``(package, level)`` pairs that
          set per-package log levels.  An empty string ``""`` for the package
          name sets the global (root) default.  Example::

              configure_worker(queue, level=[
                  ("", logging.WARNING),       # root default
                  ("disco", logging.DEBUG),    # verbose for disco package
                  ("urllib3", logging.ERROR),  # quiet for urllib3
              ])

    keep_existing_handlers:
        If False (default), remove existing handlers from the root logger
        to avoid duplicate logging. Set to True if you explicitly want
        extra handlers in the worker process.
    """
    _apply_level_config(level)

    root = logging.getLogger()
    if not keep_existing_handlers:
        root.handlers.clear()

    qh = logging.handlers.QueueHandler(queue)
    root.addHandler(qh)


# --- API-compatible helpers -------------------------------------------------


def getLogger(name: Optional[str] = None) -> logging.Logger:
    """
    Thin wrapper around logging.getLogger.

    Exposed here so users can do:

        from disco_tools.mp_logging import getLogger

    and keep the usual logging API.
    """
    return logging.getLogger(name)


# Convenience functions mirroring logging.<level>() on the root logger.

def debug(msg: object, *args: object, **kwargs: Any) -> None:
    logging.getLogger().debug(msg, *args, **kwargs)


def info(msg: object, *args: object, **kwargs: Any) -> None:
    logging.getLogger().info(msg, *args, **kwargs)


def warning(msg: object, *args: object, **kwargs: Any) -> None:
    logging.getLogger().warning(msg, *args, **kwargs)


def error(msg: object, *args: object, **kwargs: Any) -> None:
    logging.getLogger().error(msg, *args, **kwargs)


def exception(
    msg: object,
    *args: object,
    exc_info: bool = True,
    **kwargs: Any,
) -> None:
    logging.getLogger().exception(msg, *args, exc_info=exc_info, **kwargs)


def critical(msg: object, *args: object, **kwargs: Any) -> None:
    logging.getLogger().critical(msg, *args, **kwargs)
