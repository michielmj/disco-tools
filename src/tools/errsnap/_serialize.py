"""
errsnap._serialize
~~~~~~~~~~~~~~~~~~
Recursively sanitise an arbitrary Python object so that it can always be
pickled.  Unpicklable subtrees are replaced with :class:`PickleSkipped`
placeholders that record the type, a truncated ``repr``, and the failure
reason.

Only the four built-in container types are decomposed recursively:
``dict``, ``list``, ``tuple``, ``set`` / ``frozenset``.
All other objects are tried as-is; if they fail they become a
:class:`PickleSkipped` leaf.  Object attributes are intentionally **not**
introspected — attempting to reconstruct a partially-safe copy of an
arbitrary object without its class cooperation would produce a broken
object and is more surprising than a clean placeholder.

Typical usage (from ``_writer.py``)::

    from ._serialize import safe_serialize, PickleSkipped

    state_bytes, skipped = safe_serialize(state, max_depth=10)
    # state_bytes is always valid pickle bytes
    # skipped is a list of dot/bracket paths that were replaced
"""
from __future__ import annotations

import pickle
from dataclasses import dataclass
from typing import Any

_REPR_MAX = 200  # max characters kept from repr()


# ---------------------------------------------------------------------------
# Public placeholder type
# ---------------------------------------------------------------------------


@dataclass
class PickleSkipped:
    """Placeholder inserted in the state when a value could not be pickled.

    Instances of this class are always picklable and will appear in the
    loaded state wherever the original value was unpicklable.

    Attributes
    ----------
    type_name:
        Fully qualified type name of the original object,
        e.g. ``"sqlalchemy.orm.session.Session"``.
    repr_str:
        Truncated ``repr()`` of the original object (at most
        ``_REPR_MAX`` characters).
    reason:
        Error description from the failing ``pickle.dumps`` call,
        e.g. ``"TypeError: cannot pickle 'socket' object"``.
    """

    type_name: str
    repr_str: str
    reason: str

    def __repr__(self) -> str:
        return (
            f"<PickleSkipped "
            f"type={self.type_name!r} "
            f"repr={self.repr_str!r} "
            f"reason={self.reason!r}>"
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _make_skipped(obj: Any, exc: Exception) -> PickleSkipped:
    """Build a :class:`PickleSkipped` from a live object and the exception."""
    try:
        type_name = f"{type(obj).__module__}.{type(obj).__qualname__}"
    except Exception:  # noqa: BLE001
        type_name = "(unknown type)"

    try:
        r = repr(obj)
        repr_str = r if len(r) <= _REPR_MAX else r[:_REPR_MAX] + "…"
    except Exception:  # noqa: BLE001
        repr_str = "(repr failed)"

    return PickleSkipped(
        type_name=type_name,
        repr_str=repr_str,
        reason=f"{type(exc).__name__}: {exc}",
    )


def _make_depth_skipped(obj: Any) -> PickleSkipped:
    """Build a :class:`PickleSkipped` because the recursion depth was exceeded."""
    try:
        type_name = f"{type(obj).__module__}.{type(obj).__qualname__}"
    except Exception:  # noqa: BLE001
        type_name = "(unknown type)"

    return PickleSkipped(
        type_name=type_name,
        repr_str="(max_depth exceeded — not inspected)",
        reason="max_depth exceeded",
    )


def _sanitize(
    obj: Any,
    path: str,
    depth: int,
    max_depth: int,
    skipped: list[str],
) -> Any:
    """Return a picklable copy of *obj*, replacing unpicklable subtrees.

    Parameters
    ----------
    obj:
        The object to sanitise at the current level.
    path:
        Dot/bracket path from the root (used in the *skipped* report).
    depth:
        Current recursion depth (starts at 0 for the root).
    max_depth:
        Recursion limit.  Objects at depth > *max_depth* are replaced.
    skipped:
        Mutable list accumulating paths of replaced values.
    """
    # --- depth guard ------------------------------------------------------
    if depth > max_depth:
        skipped.append(path)
        return _make_depth_skipped(obj)

    # --- fast path: try the whole subtree first ---------------------------
    # This is the common case: most objects are picklable as-is.
    try:
        pickle.dumps(obj)
        return obj
    except Exception:  # noqa: BLE001
        pass  # fall through to structural decomposition

    # --- structural decomposition (only for known container types) --------
    if isinstance(obj, dict):
        return {
            k: _sanitize(
                v,
                f"{path}.{k}" if path else str(k),
                depth + 1,
                max_depth,
                skipped,
            )
            for k, v in obj.items()
        }

    if isinstance(obj, (list, tuple)):
        sanitized = [
            _sanitize(
                item,
                f"{path}[{i}]",
                depth + 1,
                max_depth,
                skipped,
            )
            for i, item in enumerate(obj)
        ]
        return type(obj)(sanitized)  # preserve list vs tuple

    if isinstance(obj, (set, frozenset)):
        sanitized = [
            _sanitize(
                item,
                f"{path}[{i}]",
                depth + 1,
                max_depth,
                skipped,
            )
            for i, item in enumerate(obj)
        ]
        return type(obj)(sanitized)

    # --- non-decomposable leaf: replace with placeholder ------------------
    try:
        pickle.dumps(obj)  # one more attempt (shouldn't reach here, but safe)
        return obj
    except Exception as exc:  # noqa: BLE001
        skipped.append(path)
        return _make_skipped(obj, exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def safe_serialize(obj: Any, max_depth: int = 10) -> tuple[bytes, list[str]]:
    """Pickle *obj*, replacing any unpicklable subtrees with :class:`PickleSkipped`.

    Decomposition is applied recursively for ``dict``, ``list``, ``tuple``,
    ``set``, and ``frozenset``.  Any other object that cannot be pickled as a
    whole is replaced with a :class:`PickleSkipped` placeholder; its internal
    attributes are **not** introspected.

    Parameters
    ----------
    obj:
        Arbitrary Python object to serialize.
    max_depth:
        Maximum recursion depth for structural decomposition.  Subtrees
        deeper than this limit are replaced with :class:`PickleSkipped`
        rather than recursed into.  Default is ``10``.

    Returns
    -------
    bytes
        Pickled bytes of the sanitized object.  **Always succeeds.**
    list[str]
        Dot / bracket paths of values that were replaced with
        :class:`PickleSkipped` placeholders, e.g.
        ``["session", "graph[2]"]``.
        Empty if nothing was skipped.
    """
    skipped: list[str] = []
    sanitized = _sanitize(obj, path="", depth=0, max_depth=max_depth, skipped=skipped)
    # Strip leading "." from dict-key paths (root="", child=".key" → "key").
    # If the root object itself was unpicklable the path is ""; use "<root>".
    skipped = [p.lstrip(".") or "<root>" for p in skipped]
    return pickle.dumps(sanitized), skipped
