"""
tests/errsnap/test_errsnap.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Flat pytest suite for the ``errsnap`` subpackage.

Run from the project root::

    pytest tests/errsnap/

All tests use ``tmp_path`` (built-in pytest fixture) for isolation.
No test classes are used.
"""
from __future__ import annotations

import io
import logging
import pickle
import zipfile
from pathlib import Path
from typing import Any

import pytest

import tools.errsnap as errsnap
from tools.errsnap import CaptureContext, DumpFile, DumpMeta, PickleSkipped
from tools.errsnap._serialize import safe_serialize
from tools.errsnap._reader import _UnpicklableState
from tools.errsnap._writer import _make_unique_path, _resolve_stem


# ---------------------------------------------------------------------------
# Module-level helpers (not fixtures)
# ---------------------------------------------------------------------------

def _capture_exc(
    state: Any,
    tmp_path: Path,
    exc: BaseException | None = None,
    stem: str = "test",
) -> CaptureContext:
    """Run ``errsnap.capture`` with a deliberate exception and return the context.

    The exception is always swallowed here; callers inspect ``ctx.dump_path``.
    """
    raised = exc if exc is not None else ValueError("test error")
    ctx = errsnap.capture(state, filename=tmp_path / stem)
    with pytest.raises(type(raised)):
        with ctx:
            raise raised
    return ctx


def _load_from(ctx: CaptureContext) -> DumpFile:
    """Convenience: assert dump_path is set and load it."""
    assert ctx.dump_path is not None
    return errsnap.load(ctx.dump_path)


# ===========================================================================
# _resolve_stem
# ===========================================================================

def test_resolve_stem_strips_py_suffix(tmp_path: Path) -> None:
    # A .py path (e.g. __file__) keeps only the stem; directory is always cwd.
    directory, stem = _resolve_stem(tmp_path / "mymodule.py", stack_depth=1)
    assert stem == "mymodule"
    assert directory == Path.cwd()


def test_resolve_stem_plain_path_kept_as_is(tmp_path: Path) -> None:
    directory, stem = _resolve_stem(tmp_path / "custom_name", stack_depth=1)
    assert stem == "custom_name"
    assert directory == tmp_path


def test_resolve_stem_none_derives_from_caller() -> None:
    # When filename is None the stem is derived from the first non-errsnap
    # frame in the call stack — i.e. this test file.
    directory, stem = _resolve_stem(None, stack_depth=1)
    assert stem  # non-empty
    assert ".py" not in stem
    assert isinstance(directory, Path)


def test_resolve_stem_errsnap_extension_uses_stem(tmp_path: Path) -> None:
    p = tmp_path / "run_20250101T000000_001.errsnap"
    directory, stem = _resolve_stem(p, stack_depth=1)
    assert stem == "run_20250101T000000_001"
    assert directory == tmp_path


# ===========================================================================
# _make_unique_path
# ===========================================================================

def test_make_unique_path_first_slot_is_001(tmp_path: Path) -> None:
    p = _make_unique_path(tmp_path, "mod", "20250310T120000")
    assert p.name == "mod_20250310T120000_001.errsnap"


def test_make_unique_path_increments_when_slot_taken(tmp_path: Path) -> None:
    (tmp_path / "mod_20250310T120000_001.errsnap").touch()
    p = _make_unique_path(tmp_path, "mod", "20250310T120000")
    assert p.name == "mod_20250310T120000_002.errsnap"


def test_make_unique_path_skips_all_occupied_slots(tmp_path: Path) -> None:
    for i in range(1, 4):
        (tmp_path / f"mod_20250310T120000_{i:03d}.errsnap").touch()
    p = _make_unique_path(tmp_path, "mod", "20250310T120000")
    assert p.name == "mod_20250310T120000_004.errsnap"


# ===========================================================================
# capture() — basic behaviour
# ===========================================================================

def test_capture_reraises_exception(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="boom"):
        with errsnap.capture({"x": 1}, filename=tmp_path / "test"):
            raise RuntimeError("boom")


def test_capture_no_exception_leaves_dump_path_none(tmp_path: Path) -> None:
    ctx = errsnap.capture({"x": 1}, filename=tmp_path / "test")
    with ctx:
        pass
    assert ctx.dump_path is None


def test_capture_creates_file_on_exception(tmp_path: Path) -> None:
    ctx = _capture_exc({"x": 1}, tmp_path)
    assert ctx.dump_path is not None
    assert ctx.dump_path.exists()


def test_capture_dump_has_errsnap_extension(tmp_path: Path) -> None:
    ctx = _capture_exc(None, tmp_path)
    assert ctx.dump_path is not None
    assert ctx.dump_path.suffix == ".errsnap"


def test_capture_dump_is_valid_zip(tmp_path: Path) -> None:
    ctx = _capture_exc({"x": 1}, tmp_path)
    assert ctx.dump_path is not None
    assert zipfile.is_zipfile(ctx.dump_path)


def test_capture_zip_contains_meta_json(tmp_path: Path) -> None:
    ctx = _capture_exc(None, tmp_path)
    assert ctx.dump_path is not None
    with zipfile.ZipFile(ctx.dump_path) as zf:
        assert "meta.json" in zf.namelist()


def test_capture_zip_contains_traceback_txt(tmp_path: Path) -> None:
    ctx = _capture_exc(None, tmp_path)
    assert ctx.dump_path is not None
    with zipfile.ZipFile(ctx.dump_path) as zf:
        assert "traceback.txt" in zf.namelist()


def test_capture_zip_contains_state_pkl_for_picklable_state(tmp_path: Path) -> None:
    ctx = _capture_exc({"a": 1}, tmp_path)
    assert ctx.dump_path is not None
    with zipfile.ZipFile(ctx.dump_path) as zf:
        assert "state.pkl" in zf.namelist()


def test_capture_state_roundtrips_via_pickle(tmp_path: Path) -> None:
    state = {"a": 1, "b": [1, 2, 3]}
    ctx = _capture_exc(state, tmp_path)
    assert ctx.dump_path is not None
    with zipfile.ZipFile(ctx.dump_path) as zf:
        recovered = pickle.loads(zf.read("state.pkl"))  # noqa: S301
    assert recovered == state


def test_capture_filename_dunder_file_strips_py() -> None:
    # Passing a .py path (e.g. __file__) uses only the stem; dump goes to cwd.
    import tempfile, os
    fake_file = "/some/deep/path/mymodule.py"
    ctx2 = errsnap.capture(None, filename=fake_file)
    with pytest.raises(ValueError):
        with ctx2:
            raise ValueError("x")
    assert ctx2.dump_path is not None
    assert ctx2.dump_path.parent == Path.cwd()
    assert ctx2.dump_path.name.startswith("mymodule_")
    ctx2.dump_path.unlink(missing_ok=True)  # clean up from cwd


def test_capture_consecutive_dumps_have_unique_paths(tmp_path: Path) -> None:
    paths = [_capture_exc(None, tmp_path).dump_path for _ in range(3)]
    assert len(set(paths)) == 3


def test_capture_sequence_numbers_are_ascending(tmp_path: Path) -> None:
    paths = [_capture_exc(None, tmp_path).dump_path for _ in range(3)]
    seq = [int(p.stem.rsplit("_", 1)[-1]) for p in paths if p is not None]
    assert seq == sorted(seq)


# ---------------------------------------------------------------------------
# Unpicklable state
# ---------------------------------------------------------------------------

def test_capture_unpicklable_state_sets_pickle_ok_false(tmp_path: Path) -> None:
    # A lambda is replaced by PickleSkipped; pickle_ok=False, skipped_paths non-empty.
    ctx = _capture_exc(lambda: None, tmp_path)
    dump = _load_from(ctx)
    assert dump.meta.pickle_ok is False
    assert dump.meta.skipped_paths  # at least one path skipped
    assert dump.meta.pickle_error is None  # not a catastrophic failure


def test_capture_unpicklable_state_writes_state_pkl(tmp_path: Path) -> None:
    # safe_serialize always writes state.pkl (with PickleSkipped placeholders).
    ctx = _capture_exc(lambda: None, tmp_path)
    assert ctx.dump_path is not None
    with zipfile.ZipFile(ctx.dump_path) as zf:
        assert "state.pkl" in zf.namelist()


def test_capture_unpicklable_state_yields_pickle_skipped_on_load(tmp_path: Path) -> None:
    # The root value is replaced with a PickleSkipped placeholder.
    ctx = _capture_exc(lambda: None, tmp_path)
    dump = _load_from(ctx)
    assert isinstance(dump.state, PickleSkipped)
    assert "function" in dump.state.type_name





# ===========================================================================
# safe_serialize
# ===========================================================================

def test_safe_serialize_picklable_object_unchanged() -> None:
    data = {"x": 1, "y": [2, 3]}
    state_bytes, skipped = safe_serialize(data)
    assert skipped == []
    assert pickle.loads(state_bytes) == data  # noqa: S301


def test_safe_serialize_unpicklable_root_replaced() -> None:
    state_bytes, skipped = safe_serialize(lambda: None)
    result = pickle.loads(state_bytes)  # noqa: S301
    assert isinstance(result, PickleSkipped)
    assert skipped == ["<root>"]


def test_safe_serialize_unpicklable_dict_value_replaced() -> None:
    data = {"good": 42, "bad": lambda: None}
    state_bytes, skipped = safe_serialize(data)
    result = pickle.loads(state_bytes)  # noqa: S301
    assert result["good"] == 42
    assert isinstance(result["bad"], PickleSkipped)
    assert skipped == ["bad"]


def test_safe_serialize_nested_unpicklable_replaced() -> None:
    data = {"outer": {"inner": lambda: None, "ok": 99}}
    state_bytes, skipped = safe_serialize(data)
    result = pickle.loads(state_bytes)  # noqa: S301
    assert result["outer"]["ok"] == 99
    assert isinstance(result["outer"]["inner"], PickleSkipped)
    assert skipped == ["outer.inner"]


def test_safe_serialize_list_element_replaced() -> None:
    data = [1, lambda: None, 3]
    state_bytes, skipped = safe_serialize(data)
    result = pickle.loads(state_bytes)  # noqa: S301
    assert result[0] == 1
    assert isinstance(result[1], PickleSkipped)
    assert result[2] == 3
    assert skipped == ["[1]"]


def test_safe_serialize_tuple_preserved() -> None:
    data = (1, 2, 3)
    state_bytes, skipped = safe_serialize(data)
    result = pickle.loads(state_bytes)  # noqa: S301
    assert result == (1, 2, 3)
    assert skipped == []


def test_safe_serialize_tuple_with_bad_element() -> None:
    data = (1, lambda: None)
    state_bytes, skipped = safe_serialize(data)
    result = pickle.loads(state_bytes)  # noqa: S301
    assert isinstance(result, tuple)
    assert result[0] == 1
    assert isinstance(result[1], PickleSkipped)


def test_safe_serialize_pickle_skipped_has_type_name() -> None:
    state_bytes, _ = safe_serialize(lambda: None)
    result = pickle.loads(state_bytes)  # noqa: S301
    assert "function" in result.type_name


def test_safe_serialize_pickle_skipped_has_reason() -> None:
    state_bytes, _ = safe_serialize(lambda: None)
    result = pickle.loads(state_bytes)  # noqa: S301
    assert result.reason  # non-empty


def test_safe_serialize_max_depth_respected(tmp_path: Path) -> None:
    # Build a deeply nested dict; with max_depth=2 the innermost value
    # is skipped rather than recursed into.
    data: Any = {"a": {"b": {"c": lambda: None}}}
    _, skipped_deep = safe_serialize(data, max_depth=10)
    _, skipped_shallow = safe_serialize(data, max_depth=1)
    # Deep: reaches the lambda and skips it at "a.b.c"
    assert "a.b.c" in skipped_deep
    # Shallow: stops at depth 1, skips "a.b" entirely (depth limit)
    assert any("a.b" in p for p in skipped_shallow)


def test_safe_serialize_multiple_skipped_paths() -> None:
    data = {"a": lambda: None, "b": lambda: None, "c": 42}
    _, skipped = safe_serialize(data)
    assert sorted(skipped) == ["a", "b"]


def test_capture_partial_state_preserved(tmp_path: Path) -> None:
    # When a dict contains a mix of good and bad values, the good values
    # are fully preserved in the dump.
    state = {"safe": {"nested": [1, 2, 3]}, "unsafe": lambda: None}
    ctx = _capture_exc(state, tmp_path)
    dump = _load_from(ctx)
    assert dump.state["safe"] == {"nested": [1, 2, 3]}
    assert isinstance(dump.state["unsafe"], PickleSkipped)


def test_capture_skipped_paths_in_meta(tmp_path: Path) -> None:
    state = {"a": 1, "b": lambda: None}
    ctx = _capture_exc(state, tmp_path)
    dump = _load_from(ctx)
    assert dump.meta.skipped_paths == ["b"]


def test_capture_skipped_paths_empty_for_clean_state(tmp_path: Path) -> None:
    ctx = _capture_exc({"x": 1}, tmp_path)
    dump = _load_from(ctx)
    assert dump.meta.skipped_paths == []


# ===========================================================================
# Logger integration
# ===========================================================================

def _make_logger() -> tuple[logging.Logger, list[str]]:
    """Return a logger and a list that collects its DEBUG messages."""
    messages: list[str] = []
    logger = logging.getLogger(f"errsnap_test_{id(messages)}")
    logger.setLevel(logging.DEBUG)
    class _Collector(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            messages.append(record.getMessage())

    logger.addHandler(_Collector())
    logger.propagate = False
    return logger, messages


def test_logger_no_message_without_exception(tmp_path: Path) -> None:
    logger, messages = _make_logger()
    ctx = errsnap.capture({"x": 1}, filename=tmp_path / "t", logger=logger)
    with ctx:
        pass  # no exception
    assert messages == []


def test_logger_emits_debug_on_exception(tmp_path: Path) -> None:
    logger, messages = _make_logger()
    ctx = errsnap.capture({"x": 1}, filename=tmp_path / "t", logger=logger)
    with pytest.raises(ValueError):
        with ctx:
            raise ValueError("oops")
    assert len(messages) == 1
    assert "errsnap" in messages[0]
    assert "dump written" in messages[0]


def test_logger_message_contains_dump_path(tmp_path: Path) -> None:
    logger, messages = _make_logger()
    ctx = errsnap.capture({"x": 1}, filename=tmp_path / "t", logger=logger)
    with pytest.raises(ValueError):
        with ctx:
            raise ValueError("oops")
    assert ctx.dump_path is not None
    assert str(ctx.dump_path) in messages[0]


def test_logger_message_contains_exception_type(tmp_path: Path) -> None:
    logger, messages = _make_logger()
    ctx = errsnap.capture({"x": 1}, filename=tmp_path / "t", logger=logger)
    with pytest.raises(ValueError):
        with ctx:
            raise ValueError("oops")
    assert "ValueError" in messages[0]


def test_logger_no_extra_message_for_picklable_state(tmp_path: Path) -> None:
    logger, messages = _make_logger()
    ctx = errsnap.capture({"x": 1}, filename=tmp_path / "t", logger=logger)
    with pytest.raises(ValueError):
        with ctx:
            raise ValueError("oops")
    assert len(messages) == 1  # only the "dump written" line


def test_logger_extra_message_for_unpicklable_state(tmp_path: Path) -> None:
    logger, messages = _make_logger()
    ctx = errsnap.capture(lambda: None, filename=tmp_path / "t", logger=logger)
    with pytest.raises(ValueError):
        with ctx:
            raise ValueError("oops")
    assert len(messages) == 2
    assert "pickle" in messages[1].lower()


def test_logger_pickle_message_contains_dump_path(tmp_path: Path) -> None:
    logger, messages = _make_logger()
    ctx = errsnap.capture(lambda: None, filename=tmp_path / "t", logger=logger)
    with pytest.raises(ValueError):
        with ctx:
            raise ValueError("oops")
    assert ctx.dump_path is not None
    assert str(ctx.dump_path) in messages[1]


def test_no_logger_still_works(tmp_path: Path) -> None:
    """Omitting logger= must not change behaviour."""
    ctx = errsnap.capture({"x": 1}, filename=tmp_path / "t")
    with pytest.raises(ValueError):
        with ctx:
            raise ValueError("oops")
    assert ctx.dump_path is not None

# ===========================================================================
# DumpMeta content
# ===========================================================================

def test_meta_exc_type_is_fully_qualified(tmp_path: Path) -> None:
    ctx = _capture_exc(None, tmp_path, exc=ValueError("oops"))
    assert _load_from(ctx).meta.exc_type == "builtins.ValueError"


def test_meta_exc_message_matches(tmp_path: Path) -> None:
    ctx = _capture_exc(None, tmp_path, exc=ValueError("my message"))
    assert _load_from(ctx).meta.exc_message == "my message"


def test_meta_timestamp_is_utc_aware(tmp_path: Path) -> None:
    ctx = _capture_exc(None, tmp_path)
    dt = _load_from(ctx).meta.timestamp_dt
    assert dt.tzinfo is not None


def test_meta_lineno_is_positive(tmp_path: Path) -> None:
    ctx = _capture_exc(None, tmp_path)
    assert _load_from(ctx).meta.lineno > 0


def test_meta_func_is_non_empty(tmp_path: Path) -> None:
    ctx = _capture_exc(None, tmp_path)
    assert _load_from(ctx).meta.func


def test_meta_pickle_ok_true_for_picklable_state(tmp_path: Path) -> None:
    ctx = _capture_exc({"x": 1}, tmp_path)
    meta = _load_from(ctx).meta
    assert meta.pickle_ok is True
    assert meta.pickle_error is None


def test_meta_errsnap_version_present(tmp_path: Path) -> None:
    ctx = _capture_exc(None, tmp_path)
    assert _load_from(ctx).meta.errsnap_version == "1"


# ===========================================================================
# DumpMeta serialisation round-trip
# ===========================================================================

def test_dump_meta_to_dict_from_dict_roundtrip(tmp_path: Path) -> None:
    ctx = _capture_exc(None, tmp_path, exc=TypeError("round-trip"))
    original_meta = _load_from(ctx).meta
    reconstructed = DumpMeta.from_dict(original_meta.to_dict())
    assert reconstructed == original_meta


def test_dump_meta_to_dict_contains_all_keys(tmp_path: Path) -> None:
    ctx = _capture_exc(None, tmp_path)
    d = _load_from(ctx).meta.to_dict()
    required = {
        "errsnap_version", "exc_type", "exc_message", "filename",
        "lineno", "func", "module", "timestamp", "pickle_ok", "pickle_error",
    }
    assert required.issubset(d.keys())


# ===========================================================================
# load()
# ===========================================================================

def test_load_returns_dumpfile_instance(tmp_path: Path) -> None:
    ctx = _capture_exc({"k": "v"}, tmp_path)
    assert ctx.dump_path is not None
    assert isinstance(errsnap.load(ctx.dump_path), DumpFile)


def test_load_accepts_str_path(tmp_path: Path) -> None:
    ctx = _capture_exc(None, tmp_path)
    assert ctx.dump_path is not None
    dump = errsnap.load(str(ctx.dump_path))
    assert isinstance(dump, DumpFile)


def test_load_accepts_path_object(tmp_path: Path) -> None:
    ctx = _capture_exc(None, tmp_path)
    assert ctx.dump_path is not None
    dump = errsnap.load(ctx.dump_path)
    assert isinstance(dump, DumpFile)


def test_load_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        errsnap.load(tmp_path / "nonexistent.errsnap")


def test_load_bad_zip_raises_bad_zip_file(tmp_path: Path) -> None:
    bad = tmp_path / "bad.errsnap"
    bad.write_bytes(b"not a zip file")
    with pytest.raises(zipfile.BadZipFile):
        errsnap.load(bad)


def test_load_recovers_state(tmp_path: Path) -> None:
    state = [1, 2, {"nested": True}]
    ctx = _capture_exc(state, tmp_path)
    assert _load_from(ctx).state == state


def test_load_traceback_contains_exception_class(tmp_path: Path) -> None:
    ctx = _capture_exc(None, tmp_path, exc=ValueError("trace me"))
    assert "ValueError" in _load_from(ctx).traceback


def test_load_traceback_contains_exception_message(tmp_path: Path) -> None:
    ctx = _capture_exc(None, tmp_path, exc=ValueError("trace me"))
    assert "trace me" in _load_from(ctx).traceback


def test_load_dump_path_is_absolute(tmp_path: Path) -> None:
    ctx = _capture_exc(None, tmp_path)
    assert ctx.dump_path is not None
    dump = errsnap.load(ctx.dump_path)
    assert dump.path.is_absolute()


def test_load_corrupted_state_pkl_returns_unpicklable_state(tmp_path: Path) -> None:
    """State that pickled fine at capture time but can't be unpickled at load time."""
    ctx = _capture_exc({"ok": True}, tmp_path)
    assert ctx.dump_path is not None
    # Overwrite state.pkl with garbage while preserving the other entries.
    original_bytes = ctx.dump_path.read_bytes()
    with zipfile.ZipFile(ctx.dump_path, "w", compression=zipfile.ZIP_DEFLATED) as zf_out:
        with zipfile.ZipFile(io.BytesIO(original_bytes)) as zf_in:
            for name in zf_in.namelist():
                data = b"corrupted pickle bytes" if name == "state.pkl" else zf_in.read(name)
                zf_out.writestr(name, data)

    dump = errsnap.load(ctx.dump_path)
    assert isinstance(dump.state, _UnpicklableState)
    assert dump.state.raw_bytes == b"corrupted pickle bytes"
    assert dump.state.reason  # non-empty explanation


# ===========================================================================
# DumpFile.summary()
# ===========================================================================

def test_summary_returns_string(tmp_path: Path) -> None:
    ctx = _capture_exc(None, tmp_path)
    assert isinstance(_load_from(ctx).summary(), str)


def test_summary_contains_exception_type(tmp_path: Path) -> None:
    ctx = _capture_exc(None, tmp_path, exc=TypeError("bad type"))
    assert "TypeError" in _load_from(ctx).summary()


def test_summary_contains_exception_message(tmp_path: Path) -> None:
    ctx = _capture_exc(None, tmp_path, exc=ValueError("hello summary"))
    assert "hello summary" in _load_from(ctx).summary()


def test_summary_contains_traceback_header(tmp_path: Path) -> None:
    ctx = _capture_exc(None, tmp_path, exc=ValueError("check traceback"))
    assert "Traceback" in _load_from(ctx).summary()


def test_summary_contains_date_portion_of_timestamp(tmp_path: Path) -> None:
    ctx = _capture_exc(None, tmp_path)
    dump = _load_from(ctx)
    date_part = dump.meta.timestamp[:10]  # "YYYY-MM-DD"
    assert date_part in dump.summary()


def test_summary_contains_dump_filename(tmp_path: Path) -> None:
    ctx = _capture_exc(None, tmp_path)
    assert ctx.dump_path is not None
    dump = errsnap.load(ctx.dump_path)
    assert ctx.dump_path.name in dump.summary()


def test_summary_mentions_pickle_failure(tmp_path: Path) -> None:
    ctx = _capture_exc(lambda: None, tmp_path)
    s = _load_from(ctx).summary()
    assert "FAILED" in s or "pickle" in s.lower()


def test_summary_mentions_pickle_success(tmp_path: Path) -> None:
    ctx = _capture_exc({"x": 1}, tmp_path)
    s = _load_from(ctx).summary()
    # The checkmark or "successfully" word should appear.
    assert "✓" in s or "successfully" in s.lower()
