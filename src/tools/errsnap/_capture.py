"""
errsnap._capture
~~~~~~~~~~~~~~~~
``capture()`` context manager.
"""
from __future__ import annotations

import inspect
import os
from pathlib import Path
from types import TracebackType
from typing import Any, Literal

from ._writer import write_dump


class CaptureContext:
    """Context manager that writes an ``.errsnap`` dump on exception.

    Do not instantiate directly — use :func:`capture`.

    The exception is **always re-raised** after the dump is written.

    Parameters
    ----------
    state:
        Any object whose state should be pickled into the dump.
    filename:
        Optional path hint.  Accepted forms:

        - ``None`` — derive the stem from the caller's source file via
          ``inspect.stack()``.
        - A ``__file__``-style path ending in ``.py`` — the ``.py`` suffix is
          stripped and the directory is used as the dump location.
        - Any other string / ``Path`` — used as the base name (directory
          component is respected; suffix may be omitted).

    Attributes
    ----------
    dump_path:
        ``Path`` of the written dump file, set after an exception is handled.
        ``None`` if no exception occurred or before the context exits.
    """

    __slots__ = ("_state", "_filename", "_caller_frame", "dump_path")

    def __init__(
        self,
        state: Any,
        filename: str | os.PathLike[str] | None = None,
    ) -> None:
        self._state = state
        self._filename = filename
        # Capture the frame of the *caller* of capture() right away so we
        # have accurate location metadata even if the stack is unwound later.
        self._caller_frame: inspect.FrameInfo | None = None
        self.dump_path: Path | None = None

    def __enter__(self) -> "CaptureContext":
        # Walk up two frames: __enter__ → capture() → actual caller
        stack = inspect.stack()
        # stack[0] = __enter__, stack[1] = capture() or direct __enter__ call
        # We want the frame that contains the ``with`` statement.
        for frame_info in stack[1:]:
            # Skip frames that live inside the errsnap package itself.
            pkg = Path(__file__).parent.resolve()
            src = Path(frame_info.filename).resolve()
            try:
                src.relative_to(pkg)
            except ValueError:
                self._caller_frame = frame_info
                break
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        tb: TracebackType | None,
    ) -> Literal[False]:
        if exc_type is None:
            # No exception — nothing to do.
            return False

        # When exc_type is not None the other two parameters are always set by
        # the interpreter; assert here so mypy narrows away the | None.
        assert exc_val is not None
        assert tb is not None

        self.dump_path = write_dump(
            state=self._state,
            exc=exc_val,
            exc_type=exc_type,
            tb=tb,
            filename=self._filename,
            caller_frame=self._caller_frame,
        )

        # Always re-raise.
        return False


def capture(
    state: Any,
    *,
    filename: str | os.PathLike[str] | None = None,
) -> CaptureContext:
    """Return a context manager that dumps *state* to a ``.errsnap`` file on exception.

    Example usage::

        with errsnap.capture(my_state, filename=__file__):
            run_simulation()

        # filename omitted → derived automatically from the caller's __file__
        with errsnap.capture(my_state):
            run_simulation()

    Parameters
    ----------
    state:
        Arbitrary object to snapshot.  Use a ``dict`` or ``list`` to bundle
        multiple objects together.
    filename:
        Base path for the dump file.  Pass ``__file__`` from your module to
        place the dump next to your source file (the ``.py`` suffix is stripped
        automatically).  If omitted, ``errsnap`` resolves the caller's source
        file via ``inspect.stack()``.

    Returns
    -------
    CaptureContext
        A context manager.  After an exception, ``ctx.dump_path`` holds the
        ``Path`` of the written dump file.
    """
    return CaptureContext(state=state, filename=filename)
