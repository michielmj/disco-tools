"""
errsnap._writer
~~~~~~~~~~~~~~~
Serialises an exception snapshot to a ``.errsnap`` zip archive.
"""
from __future__ import annotations

import datetime
import glob
import inspect
import json
import os
import pickle
import traceback
import zipfile
from pathlib import Path
from typing import Tuple
from types import TracebackType
from typing import Any

from ._types import DumpMeta

# ---------------------------------------------------------------------------
# Internal constants
# ---------------------------------------------------------------------------

_STATE_ENTRY = "state.pkl"
_META_ENTRY = "meta.json"
_TB_ENTRY = "traceback.txt"
_EXTENSION = ".errsnap"


# ---------------------------------------------------------------------------
# Filename resolution
# ---------------------------------------------------------------------------

def _resolve_stem(filename: str | os.PathLike[str] | None, stack_depth: int) -> tuple[Path, str]:
    """Return *(directory, stem)* for the dump file.

    *directory* is the directory in which the dump file will be written.
    *stem* is the base name without timestamp, sequence, or extension.

    Rules
    -----
    - If *filename* is ``None``, derive the stem from the caller's ``__file__``
      via the call stack and write to the **current working directory**.
    - If *filename* ends with ``.py`` (the caller passed ``__file__`` directly),
      use only the stem and write to the **current working directory**.
    - Otherwise treat *filename* as an explicit path: the stem is the final
      component and the directory is the parent (defaulting to cwd when no
      parent directory is specified).
    """
    if filename is None:
        # Climb the stack to find the first frame outside this package.
        pkg_dir = Path(__file__).parent.resolve()
        for frame_info in inspect.stack()[stack_depth:]:
            caller_file = frame_info.filename
            if caller_file and "<" not in caller_file:
                caller_path = Path(caller_file).resolve()
                if pkg_dir not in caller_path.parents:
                    return Path.cwd(), caller_path.stem
        # Ultimate fallback.
        return Path.cwd(), "errsnap_dump"

    path = Path(filename)
    # Strip .py if the caller passed __file__ — dump goes to cwd.
    if path.suffix.lower() == ".py":
        return Path.cwd(), path.stem

    # Explicit path: honour the directory component if one was given.
    stem = path.stem if path.suffix == _EXTENSION else path.name
    directory = path.parent if path.parent != Path(".") else Path.cwd()
    return directory, stem


def _make_unique_path(directory: Path, stem: str, ts: str) -> Path:
    """Return a path ``<directory>/<stem>_<ts>_NNN.errsnap`` that does not exist.

    *ts* is the timestamp string (compact ISO-like, safe for filenames).
    Scans existing files in *directory* that share the same stem and timestamp
    to determine the next available sequence number (zero-padded to 3 digits).
    """
    pattern = str(directory / f"{stem}_{ts}_*.errsnap")
    existing = glob.glob(pattern)
    seq = len(existing) + 1
    while True:
        path = directory / f"{stem}_{ts}_{seq:03d}.errsnap"
        if not path.exists():
            return path
        seq += 1


# ---------------------------------------------------------------------------
# Core writer
# ---------------------------------------------------------------------------

def write_dump(
    state: Any,
    exc: BaseException,
    exc_type: type[BaseException],
    tb: TracebackType,
    filename: str | os.PathLike[str] | None,
    caller_frame: inspect.FrameInfo | None,
) -> tuple[Path, bool]:
    """Write a ``.errsnap`` zip archive and return the path.

    Parameters
    ----------
    state:
        Arbitrary object to snapshot.
    exc:
        The live exception instance.
    exc_type:
        ``type(exc)``
    tb:
        The raw traceback object.
    filename:
        Explicit destination hint (may be ``None``).
    caller_frame:
        The ``inspect.FrameInfo`` for the ``capture()`` call site (used for
        location metadata).  If ``None``, location fields will be empty.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M%S")
    iso = now.isoformat()

    directory, stem = _resolve_stem(filename, stack_depth=3)
    directory.mkdir(parents=True, exist_ok=True)
    dump_path = _make_unique_path(directory, stem, ts)

    # --- location metadata from the caller frame -------------------------
    if caller_frame is not None:
        src_file = caller_frame.filename or ""
        src_lineno = caller_frame.lineno or 0
        src_func = caller_frame.function or ""
        src_module = (caller_frame.frame.f_globals.get("__name__") or "")
    else:
        src_file = src_func = src_module = ""
        src_lineno = 0

    # --- traceback text --------------------------------------------------
    tb_lines = traceback.format_exception(exc_type, exc, tb)
    tb_text = "".join(tb_lines)

    # --- pickle state ----------------------------------------------------
    pickle_ok = True
    pickle_error: str | None = None
    state_bytes: bytes | None = None
    try:
        state_bytes = pickle.dumps(state)
    except Exception as pickle_exc:  # noqa: BLE001
        pickle_ok = False
        pickle_error = f"{type(pickle_exc).__name__}: {pickle_exc}"

    # --- build meta ------------------------------------------------------
    meta = DumpMeta(
        exc_type=f"{exc_type.__module__}.{exc_type.__qualname__}",
        exc_message=str(exc),
        filename=src_file,
        lineno=src_lineno,
        func=src_func,
        module=src_module,
        timestamp=iso,
        pickle_ok=pickle_ok,
        pickle_error=pickle_error,
    )

    # --- write zip -------------------------------------------------------
    with zipfile.ZipFile(dump_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(_META_ENTRY, json.dumps(meta.to_dict(), indent=2))
        zf.writestr(_TB_ENTRY, tb_text)
        if state_bytes is not None:
            zf.writestr(_STATE_ENTRY, state_bytes)

    return dump_path, pickle_ok
