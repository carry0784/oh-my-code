"""
CR-NEW Unit Tests — workers.tasks.data_collection_tasks helpers.

Pure-function tests for _to_native() and _classify_failure(); no DB,
exchange, or Celery execution. Environment-independent.

Linked seal: docs/operations/evidence/cr_new_p3_window_seal_2026-04-14.md
CR: CR-NEW v3.1 (Change-1 + Change-2)
"""

from __future__ import annotations

import asyncio
import math

import pytest
from sqlalchemy.exc import OperationalError

from workers.tasks.data_collection_tasks import (
    _DETERMINISTIC_SCHEMA_MARKERS,
    _classify_failure,
    _to_native,
)


# ---------- _to_native() — Change-1 ----------


class TestToNative:
    def test_none_passthrough(self):
        assert _to_native(None) is None

    def test_native_float_passthrough(self):
        result = _to_native(3.14)
        assert result == 3.14
        assert isinstance(result, float)

    def test_native_int_passthrough(self):
        result = _to_native(42)
        assert result == 42
        assert isinstance(result, int)

    def test_native_str_passthrough(self):
        assert _to_native("hello") == "hello"

    def test_numpy_float64_converted(self):
        numpy = pytest.importorskip("numpy")
        value = numpy.float64(694.7689499999997)
        result = _to_native(value)
        assert isinstance(result, float)
        assert not isinstance(result, numpy.floating)
        assert result == pytest.approx(694.7689499999997)

    def test_numpy_int64_converted(self):
        numpy = pytest.importorskip("numpy")
        value = numpy.int64(12345)
        result = _to_native(value)
        assert isinstance(result, int)
        assert not isinstance(result, numpy.integer)
        assert result == 12345

    def test_numpy_nan_preserved(self):
        numpy = pytest.importorskip("numpy")
        value = numpy.float64("nan")
        result = _to_native(value)
        assert isinstance(result, float)
        assert math.isnan(result)

    def test_object_without_item_passthrough(self):
        class NoItem:
            pass

        obj = NoItem()
        assert _to_native(obj) is obj

    def test_item_raising_valueerror_passthrough(self):
        # If .item() raises ValueError/TypeError, return original value.
        class BadItem:
            def item(self):
                raise ValueError("cannot convert")

        obj = BadItem()
        assert _to_native(obj) is obj


# ---------- _classify_failure() — Change-2 ----------


class TestClassifyFailureDeterministic:
    def test_type_name_invalidschemaname(self):
        # Simulate psycopg2.errors.InvalidSchemaName without importing the
        # real class — classifier keys on type(exc).__name__.
        class InvalidSchemaName(Exception):
            pass

        exc = InvalidSchemaName('schema "np" does not exist')
        failure_class, retryable = _classify_failure(exc)
        assert failure_class == "deterministic_type_schema"
        assert retryable is False

    def test_schema_marker_fallback_np(self):
        # Wrapped DBAPI error (type-name does not match) — string fallback.
        exc = RuntimeError('wrapper: schema "np" does not exist')
        failure_class, retryable = _classify_failure(exc)
        assert failure_class == "deterministic_type_schema"
        assert retryable is False

    def test_schema_marker_fallback_pd(self):
        exc = RuntimeError('wrapped: schema "pd" does not exist')
        failure_class, retryable = _classify_failure(exc)
        assert failure_class == "deterministic_type_schema"
        assert retryable is False

    def test_schema_marker_fallback_numpy(self):
        exc = RuntimeError('schema "numpy" missing')
        failure_class, retryable = _classify_failure(exc)
        assert failure_class == "deterministic_type_schema"
        assert retryable is False

    def test_typeerror_numpy_keyword(self):
        exc = TypeError("cannot convert numpy.float64 to SQL parameter")
        failure_class, retryable = _classify_failure(exc)
        assert failure_class == "deterministic_type_schema"
        assert retryable is False


class TestClassifyFailureTransient:
    def test_asyncio_timeout(self):
        exc = asyncio.TimeoutError("request timed out")
        failure_class, retryable = _classify_failure(exc)
        assert failure_class == "transient_network"
        assert retryable is True

    def test_operational_error(self):
        # SQLAlchemy OperationalError signature: (statement, params, orig)
        exc = OperationalError("SELECT 1", None, Exception("connection lost"))
        failure_class, retryable = _classify_failure(exc)
        assert failure_class == "transient_db"
        assert retryable is True


class TestClassifyFailureUnknown:
    def test_generic_runtime_error(self):
        # Unknown exceptions preserve backward-compatible retry behavior.
        exc = RuntimeError("something unexpected")
        failure_class, retryable = _classify_failure(exc)
        assert failure_class == "unknown"
        assert retryable is True

    def test_typeerror_without_numpy_keyword_falls_to_unknown(self):
        # TypeError without 'numpy' marker is not deterministic — retry path.
        exc = TypeError("unrelated type error")
        failure_class, retryable = _classify_failure(exc)
        assert failure_class == "unknown"
        assert retryable is True

    def test_valueerror_is_unknown(self):
        exc = ValueError("bad value")
        failure_class, retryable = _classify_failure(exc)
        assert failure_class == "unknown"
        assert retryable is True


# ---------- Markers integrity ----------


class TestDeterministicMarkers:
    def test_markers_are_lowercase(self):
        # Classifier lowercases str(exc); markers must be lowercase for match.
        for marker in _DETERMINISTIC_SCHEMA_MARKERS:
            assert marker == marker.lower()

    def test_markers_cover_np_and_pd(self):
        combined = " ".join(_DETERMINISTIC_SCHEMA_MARKERS)
        assert '"np"' in combined
        assert '"pd"' in combined
        assert '"numpy"' in combined
        assert '"pandas"' in combined

    def test_markers_are_tuple(self):
        # Tuple is immutable — prevents accidental runtime mutation.
        assert isinstance(_DETERMINISTIC_SCHEMA_MARKERS, tuple)
