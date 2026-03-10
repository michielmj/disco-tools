"""
errsnap._reader
~~~~~~~~~~~~~~~
Load and inspect ``.errsnap`` dump files.
"""
from __future__ import annotations

import json
import os
import pickle
import textwrap
import zipfile
from pathlib import Path
from typing import Any

from ._types import DumpMeta

_STATE_ENTRY = "state.pkl"
_META_ENTRY = "meta.json"
_TB_ENTRY = "traceback.txt"


class DumpFile:
    """An opened ``.errsnap`` dump.

    Obtain an instance via :func:`load` rather than constructing directly.

    Attributes
    ----------
    path:
        Absolute ``Path`` to the dump file.
    meta:
        :class:`~errsnap.DumpMeta` with exception and location metadata.
    traceback:
        Full formatted traceback as a plain string.
    state:
        The unpickled state object.  Any values that could not be pickled
        during capture are replaced with :class:`~errsnap.PickleSkipped`
        placeholders — inspect ``meta.skipped_paths`` to see which paths
        were affected.  ``None`` only if a catastrophic pickling failure
        occurred (``meta.pickle_ok is False`` and ``state.pkl`` absent).
    """

    __slots__ = ("path", "meta", "traceback", "state")

    def __init__(
        self,
        path: Path,
        meta: DumpMeta,
        traceback: str,
        state: Any,
    ) -> None:
        self.path = path
        self.meta = meta
        self.traceback = traceback
        self.state = state

    # ------------------------------------------------------------------
    # Human-readable summary
    # ------------------------------------------------------------------

    def summary(self) -> str:
        """Return a formatted multi-line summary string.

        Includes exception metadata, location, and the full traceback.
        Does **not** describe the pickled state (the caller can inspect
        ``self.state`` directly).

        Returns
        -------
        str
            Human-readable summary, ready to print or log.
        """
        sep = "─" * 72
        lines: list[str] = [
            sep,
            f"  errsnap dump  {self.path.name}",
            sep,
            f"  Timestamp  : {self.meta.timestamp}",
            f"  Exception  : {self.meta.exc_type}",
            f"  Message    : {self.meta.exc_message or '(no message)'}",
            sep,
            f"  Captured at: {self.meta.filename}:{self.meta.lineno}",
            f"  Function   : {self.meta.func or '(unknown)'}",
            f"  Module     : {self.meta.module or '(unknown)'}",
            sep,
        ]

        if self.meta.pickle_ok:
            lines.append("  State      : pickled successfully  ✓")
        elif self.meta.skipped_paths:
            n = len(self.meta.skipped_paths)
            lines.append(f"  State      : pickled ({n} path{'s' if n != 1 else ''} skipped)  ⚠")
            for p in self.meta.skipped_paths:
                lines.append(f"               • {p}")
        else:
            lines.append(f"  State      : pickle FAILED — {self.meta.pickle_error}")

        lines += [
            sep,
            "  Traceback:",
            "",
        ]
        # Indent the traceback body for readability.
        indented_tb = textwrap.indent(self.traceback.rstrip(), "    ")
        lines.append(indented_tb)
        lines.append(sep)

        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"<DumpFile {self.path.name!r} "
            f"exc={self.meta.exc_type!r} "
            f"ts={self.meta.timestamp!r}>"
        )


# ---------------------------------------------------------------------------
# Public loader
# ---------------------------------------------------------------------------

def load(path: str | os.PathLike[str]) -> DumpFile:
    """Load a ``.errsnap`` dump file.

    Parameters
    ----------
    path:
        Path to the ``.errsnap`` file (accepts both ``str`` and
        :class:`pathlib.Path`).

    Returns
    -------
    DumpFile
        Populated :class:`DumpFile` instance.

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    zipfile.BadZipFile
        If the file is not a valid zip archive.
    KeyError
        If the archive is missing required entries (``meta.json`` or
        ``traceback.txt``).
    """
    resolved = Path(path).resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"errsnap dump not found: {resolved}")

    with zipfile.ZipFile(resolved, "r") as zf:
        names = zf.namelist()

        # --- meta --------------------------------------------------------
        if _META_ENTRY not in names:
            raise KeyError(f"Archive is missing required entry '{_META_ENTRY}'")
        meta_dict = json.loads(zf.read(_META_ENTRY).decode("utf-8"))
        meta = DumpMeta.from_dict(meta_dict)

        # --- traceback ---------------------------------------------------
        if _TB_ENTRY not in names:
            raise KeyError(f"Archive is missing required entry '{_TB_ENTRY}'")
        tb_text = zf.read(_TB_ENTRY).decode("utf-8")

        # --- state (optional) --------------------------------------------
        state: Any = None
        if _STATE_ENTRY in names:
            raw = zf.read(_STATE_ENTRY)
            try:
                state = pickle.loads(raw)  # noqa: S301
            except Exception as exc:  # noqa: BLE001
                # Surface as a clear attribute rather than crashing load().
                state = _UnpicklableState(
                    reason=f"{type(exc).__name__}: {exc}",
                    raw_bytes=raw,
                )

    return DumpFile(path=resolved, meta=meta, traceback=tb_text, state=state)


class _UnpicklableState:
    """Placeholder for state that could not be unpickled during *load*.

    This can happen when the state was pickled successfully at capture time
    but the required classes are not importable in the current environment.

    Attributes
    ----------
    reason:
        Error description from the failing ``pickle.loads`` call.
    raw_bytes:
        The raw pickle bytes, in case the caller wants to attempt a manual
        reconstruction.
    """

    __slots__ = ("reason", "raw_bytes")

    def __init__(self, reason: str, raw_bytes: bytes) -> None:
        self.reason = reason
        self.raw_bytes = raw_bytes

    def __repr__(self) -> str:
        return f"<_UnpicklableState reason={self.reason!r} bytes={len(self.raw_bytes)}>"
