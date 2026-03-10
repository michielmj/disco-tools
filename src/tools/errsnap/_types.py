"""
errsnap._types
~~~~~~~~~~~~~~
Shared data structures.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DumpMeta:
    """Metadata captured at the point of exception.

    Attributes
    ----------
    exc_type:
        Fully qualified exception class name, e.g. ``"builtins.ValueError"``.
    exc_message:
        ``str(exc)`` of the raised exception.
    filename:
        Source file in which the exception was caught (the file that owns the
        ``capture()`` context manager, not necessarily where the raise occurred).
    lineno:
        Line number of the ``with capture(...)`` statement.
    func:
        Function / method name containing the ``capture()`` block.
    module:
        Module name (``__name__``) of the calling scope, if available.
    timestamp:
        UTC time at which the dump was written (ISO-8601 string).
    pickle_ok:
        ``True`` if ``state`` was successfully pickled into ``state.pkl``.
    pickle_error:
        Human-readable reason why pickling failed, or ``None`` if it succeeded.
    errsnap_version:
        Version tag for forward-compatibility of the dump format.
    """

    exc_type: str
    exc_message: str
    filename: str
    lineno: int
    func: str
    module: str
    timestamp: str
    pickle_ok: bool
    pickle_error: str | None = None
    errsnap_version: str = "1"

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @property
    def timestamp_dt(self) -> datetime.datetime:
        """Return *timestamp* as a ``datetime.datetime`` (UTC, aware)."""
        return datetime.datetime.fromisoformat(self.timestamp)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict suitable for ``json.dumps``."""
        return {
            "errsnap_version": self.errsnap_version,
            "exc_type": self.exc_type,
            "exc_message": self.exc_message,
            "filename": self.filename,
            "lineno": self.lineno,
            "func": self.func,
            "module": self.module,
            "timestamp": self.timestamp,
            "pickle_ok": self.pickle_ok,
            "pickle_error": self.pickle_error,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DumpMeta":
        """Reconstruct from a plain dict (as loaded from ``meta.json``)."""
        return cls(
            exc_type=d["exc_type"],
            exc_message=d["exc_message"],
            filename=d["filename"],
            lineno=d["lineno"],
            func=d["func"],
            module=d.get("module", ""),
            timestamp=d["timestamp"],
            pickle_ok=d["pickle_ok"],
            pickle_error=d.get("pickle_error"),
            errsnap_version=d.get("errsnap_version", "1"),
        )
