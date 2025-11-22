"""
Public interface for the multi-process logging helpers.

Re-exports the main functions so callers can do:

    from disco_tools.mp_logging import (
        MPLoggingConfig,
        setup_logging,
        configure_worker,
        getLogger,
        info,
        error,
    )
"""

from .core import (  # noqa: F401
    MPLoggingConfig,
    configure_worker,
    setup_logging,
    getLogger,
    debug,
    info,
    warning,
    error,
    exception,
    critical,
)

__all__ = [
    "MPLoggingConfig",
    "configure_worker",
    "setup_logging",
    "getLogger",
    "debug",
    "info",
    "warning",
    "error",
    "exception",
    "critical",
]
